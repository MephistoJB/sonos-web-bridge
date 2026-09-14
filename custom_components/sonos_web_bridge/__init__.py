"""Home Assistant integration for Sonos Web Bridge."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from aiohttp import web

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_PSONO_BEARER_TOKEN,
    CONF_PSONO_BEARER_TOKEN_FILE,
    CONF_PSONO_MCP_URL,
    CONF_REFRESH_INTERVAL_HOURS,
    CONF_REFRESH_THRESHOLD_HOURS,
    CONF_SONOS_EMAIL,
    CONF_SONOS_EMAIL_KEY,
    CONF_SONOS_PASSWORD,
    CONF_SONOS_PASSWORD_KEY,
    DEFAULT_REFRESH_INTERVAL_HOURS,
    DEFAULT_REFRESH_THRESHOLD_HOURS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .psono import PsonoClient
from .sonos_web import SonosWebClient, SonosWebState

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = vol.Schema({vol.Optional("email"): str, vol.Optional("password"): str})
REFRESH_SCHEMA = vol.Schema({vol.Optional("force", default=False): bool})
SEARCH_SCHEMA = vol.Schema({vol.Required("query"): str, vol.Optional("count", default=20): vol.All(int, vol.Range(min=1, max=100))})
LIBRARY_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("count", default=100): vol.All(int, vol.Range(min=1, max=500)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos Web Bridge from a config entry."""
    store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    state = SonosWebState.from_dict(await store.async_load())
    runtime = SonosWebBridgeRuntime(hass, entry, store, state)
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await runtime.async_start()
    _register_services_once(hass)
    hass.http.register_view(SonosWebBridgeStatusView(runtime))
    hass.http.register_view(SonosWebBridgeLoginView(runtime))
    hass.http.register_view(SonosWebBridgeDiscoverView(runtime))
    hass.http.register_view(SonosWebBridgeSearchView(runtime))
    hass.http.register_view(SonosWebBridgeLibraryTracksView(runtime))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sonos Web Bridge."""
    runtime = entry.runtime_data
    await runtime.async_stop()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True


class SonosWebBridgeRuntime:
    """Runtime object for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: Store[dict[str, Any]], state: SonosWebState) -> None:
        self.hass = hass
        self.entry = entry
        self.store = store
        self.client = SonosWebClient(async_get_clientsession(hass), state)
        self._refresh_lock = asyncio.Lock()
        self._unsub_refresh = None

    async def async_start(self) -> None:
        """Start periodic refresh."""
        config = self._config
        interval_hours = int(config.get(CONF_REFRESH_INTERVAL_HOURS, DEFAULT_REFRESH_INTERVAL_HOURS))
        self._unsub_refresh = async_track_time_interval(self.hass, self._scheduled_refresh, timedelta(hours=interval_hours))
        await self.async_refresh(force=False)

    async def async_stop(self) -> None:
        """Stop periodic refresh."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    async def async_login(self, email: str | None = None, password: str | None = None) -> dict[str, Any]:
        """Login and store the resulting session."""
        email, password = await self._credentials(email, password)
        async with self._refresh_lock:
            state = await self.client.login(email, password)
            await self.store.async_save(state.as_dict())
            return self.client.status()

    async def async_refresh(self, force: bool = False) -> dict[str, Any]:
        """Refresh the session if needed."""
        config = self._config
        threshold_hours = int(config.get(CONF_REFRESH_THRESHOLD_HOURS, DEFAULT_REFRESH_THRESHOLD_HOURS))
        if not force and not self.client.needs_refresh(threshold_hours * 3600):
            return self.client.status()
        try:
            return await self.async_login()
        except Exception as err:
            _LOGGER.warning("Sonos Web session refresh failed: %s", err)
            return self.client.status() | {"refresh_error": str(err)}

    async def async_discover(self) -> dict[str, Any]:
        """Discover Sonos Web state, refreshing once if necessary."""
        try:
            result = await self.client.discover()
        except Exception:
            await self.async_refresh(force=True)
            result = await self.client.discover()
        await self.store.async_save(self.client.state.as_dict())
        return result

    async def async_search(self, query: str, count: int) -> dict[str, Any]:
        """Search Apple Music through Sonos."""
        try:
            return await self.client.search(query, count)
        except Exception:
            await self.async_refresh(force=True)
            return await self.client.search(query, count)

    async def async_library_tracks(self, offset: int, count: int) -> dict[str, Any]:
        """Browse library tracks through Sonos."""
        try:
            return await self.client.library_tracks(offset, count)
        except Exception:
            await self.async_refresh(force=True)
            return await self.client.library_tracks(offset, count)

    def status(self) -> dict[str, Any]:
        """Return non-secret status."""
        return self.client.status()

    async def _scheduled_refresh(self, _now) -> None:
        await self.async_refresh(force=False)

    @property
    def _config(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    async def _credentials(self, email: str | None, password: str | None) -> tuple[str, str]:
        if email and password:
            return email, password
        config = self._config
        stored_email = str(config.get(CONF_SONOS_EMAIL, "")).strip()
        stored_password = str(config.get(CONF_SONOS_PASSWORD, ""))
        if stored_email and stored_password:
            return stored_email, stored_password
        psono = await PsonoClient.async_from_config(
            self.hass,
            async_get_clientsession(self.hass),
            str(config.get(CONF_PSONO_MCP_URL, "")),
            str(config.get(CONF_PSONO_BEARER_TOKEN, "")),
            str(config.get(CONF_PSONO_BEARER_TOKEN_FILE, "")),
        )
        if not psono:
            raise RuntimeError("No Sonos credentials configured")
        email_key = str(config[CONF_SONOS_EMAIL_KEY])
        password_key = str(config[CONF_SONOS_PASSWORD_KEY])
        return await psono.get_secret(email_key), await psono.get_secret(password_key)


def _runtime(hass: HomeAssistant) -> SonosWebBridgeRuntime:
    runtimes = hass.data.get(DOMAIN, {})
    if not runtimes:
        raise RuntimeError("Sonos Web Bridge is not configured")
    return next(iter(runtimes.values()))


def _register_services_once(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "login"):
        return

    async def login(call: ServiceCall) -> dict[str, Any]:
        return await _runtime(hass).async_login(call.data.get("email"), call.data.get("password"))

    async def refresh(call: ServiceCall) -> dict[str, Any]:
        return await _runtime(hass).async_refresh(bool(call.data.get("force")))

    async def discover(call: ServiceCall) -> dict[str, Any]:
        return await _runtime(hass).async_discover()

    async def search(call: ServiceCall) -> dict[str, Any]:
        return await _runtime(hass).async_search(call.data["query"], call.data["count"])

    async def library_tracks(call: ServiceCall) -> dict[str, Any]:
        return await _runtime(hass).async_library_tracks(call.data["offset"], call.data["count"])

    hass.services.async_register(DOMAIN, "login", login, schema=LOGIN_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "refresh", refresh, schema=REFRESH_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "discover", discover, supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "search", search, schema=SEARCH_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "library_tracks", library_tracks, schema=LIBRARY_TRACKS_SCHEMA, supports_response=SupportsResponse.ONLY)


class _BaseView(HomeAssistantView):
    requires_auth = True

    def __init__(self, runtime: SonosWebBridgeRuntime) -> None:
        self.runtime = runtime


class SonosWebBridgeStatusView(_BaseView):
    """Return session status."""

    url = "/api/sonos_web_bridge/status"
    name = "api:sonos_web_bridge:status"

    async def get(self, request: web.Request) -> web.Response:
        return self.json(self.runtime.status())


class SonosWebBridgeLoginView(_BaseView):
    """Login using posted credentials or configured Psono."""

    url = "/api/sonos_web_bridge/login"
    name = "api:sonos_web_bridge:login"

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        result = await self.runtime.async_login(data.get("email"), data.get("password"))
        return self.json(result)


class SonosWebBridgeDiscoverView(_BaseView):
    """Discover Sonos Apple Music registration."""

    url = "/api/sonos_web_bridge/discover"
    name = "api:sonos_web_bridge:discover"

    async def get(self, request: web.Request) -> web.Response:
        return self.json(await self.runtime.async_discover())


class SonosWebBridgeSearchView(_BaseView):
    """Search Apple Music via Sonos."""

    url = "/api/sonos_web_bridge/search"
    name = "api:sonos_web_bridge:search"

    async def get(self, request: web.Request) -> web.Response:
        query = request.query.get("q", "").strip()
        if not query:
            return self.json_message("Missing q parameter", status_code=400)
        count = max(1, min(100, int(request.query.get("count", "20"))))
        return self.json(await self.runtime.async_search(query, count))


class SonosWebBridgeLibraryTracksView(_BaseView):
    """Browse Apple Music library tracks via Sonos."""

    url = "/api/sonos_web_bridge/library/tracks"
    name = "api:sonos_web_bridge:library_tracks"

    async def get(self, request: web.Request) -> web.Response:
        offset = max(0, int(request.query.get("offset", "0")))
        count = max(1, min(500, int(request.query.get("count", "100"))))
        return self.json(await self.runtime.async_library_tracks(offset, count))
