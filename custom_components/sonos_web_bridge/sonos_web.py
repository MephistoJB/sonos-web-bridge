"""Browserless Sonos Web API client."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urljoin

from aiohttp import ClientResponse, ClientSession
from yarl import URL

from .const import PLAY_SONOS_BASE, PLAY_SONOS_WEB_APP

_LOGGER = logging.getLogger(__name__)


@dataclass
class SonosCookie:
    """Serializable cookie entry."""

    name: str
    value: str
    domain: str
    path: str = "/"
    expires: int | None = None
    secure: bool = True
    http_only: bool = True


@dataclass
class SonosWebState:
    """Serializable Sonos Web session state."""

    cookies: list[SonosCookie] = field(default_factory=list)
    household_id: str = ""
    service_id: str = ""
    account_id: str = ""
    integration_id: str = "com.apple.sonos-music"
    updated_at: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SonosWebState":
        """Load state from Home Assistant storage."""
        if not data:
            return cls()
        return cls(
            cookies=[SonosCookie(**cookie) for cookie in data.get("cookies", [])],
            household_id=str(data.get("household_id", "")),
            service_id=str(data.get("service_id", "")),
            account_id=str(data.get("account_id", "")),
            integration_id=str(data.get("integration_id", "com.apple.sonos-music")),
            updated_at=int(data.get("updated_at", 0)),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize state."""
        return {
            "cookies": [cookie.__dict__ for cookie in self.cookies],
            "household_id": self.household_id,
            "service_id": self.service_id,
            "account_id": self.account_id,
            "integration_id": self.integration_id,
            "updated_at": self.updated_at,
        }

    @property
    def session_expires_at(self) -> int:
        """Return the NextAuth session cookie expiry."""
        for cookie in self.cookies:
            if cookie.name == "__Secure-next-auth.session-token" and cookie.domain == "play.sonos.com":
                return int(cookie.expires or 0)
        return 0


class SonosWebClient:
    """Client for the Sonos Web API used by play.sonos.com."""

    def __init__(self, session: ClientSession, state: SonosWebState | None = None) -> None:
        self._session = session
        self.state = state or SonosWebState()

    async def login(self, email: str, password: str) -> SonosWebState:
        """Perform the browserless Sonos Web login."""
        self.state = SonosWebState()
        csrf = await self._nextauth_csrf()
        signin = await self._fetch(
            "https://play.sonos.com/api/auth/signin/okta",
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Referer": "https://play.sonos.com/de-de/login"},
            data={"csrfToken": csrf, "callbackUrl": PLAY_SONOS_WEB_APP, "json": "true"},
        )
        signin_body = await signin.json()
        signin_url = signin_body.get("url")
        if not signin_url:
            raise RuntimeError("play.sonos.com did not return an Okta sign-in URL")

        okta_response, okta_url = await self._follow_redirects(signin_url)
        okta_html = await okta_response.text()
        okta = _extract_okta_data(okta_html)
        authn = await self._fetch(
            f"{okta['base_url']}/api/v1/authn",
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json", "Origin": okta["base_url"], "Referer": okta_url},
            json_data={
                "username": email,
                "password": password,
                "stateToken": okta["state_token"],
                "options": {"warnBeforePasswordExpired": True, "multiOptionalFactorEnroll": True},
            },
        )
        authn_body = await _response_json(authn)
        completed = await self._complete_okta_authn(okta["base_url"], authn_body)
        if not completed:
            session_token = authn_body.get("sessionToken")
            if not session_token:
                raise RuntimeError(f"Browserless Okta login did not complete automatically. Status: {authn_body.get('status', authn.status)}")
            await self._follow_redirects(f"{okta['base_url']}/login/sessionCookieRedirect?token={session_token}&redirectUrl={okta['redirect_uri']}")

        await self.discover()
        return self.state

    async def discover(self) -> dict[str, Any]:
        """Discover household and Apple Music registration."""
        households_body = await self.sonos_get("/api/control/households")
        households = _items_from_response(households_body, "households")
        if not isinstance(households, list) or not households:
            raise RuntimeError("No Sonos household found")
        household = households[0]
        household_id = str(household.get("id") or household.get("householdId") or "")
        if not household_id:
            raise RuntimeError("No Sonos household id found")

        registrations = await self.sonos_get(f"/api/content/v1/households/{household_id}/integrations/registrations")
        registration_items = _items_from_response(registrations, "registrations")
        apple = next((item for item in registration_items if "apple" in json.dumps(item).lower()), None)
        if not apple:
            raise RuntimeError("Apple Music is not registered in this Sonos household")

        self.state.household_id = household_id
        self.state.service_id = str(apple.get("serviceId") or apple.get("service-id") or apple.get("service", {}).get("id") or apple.get("id"))
        self.state.account_id = str(apple.get("accountId") or apple.get("account-id") or apple.get("account", {}).get("id"))
        self.state.integration_id = str(apple.get("integrationId") or apple.get("integration-id") or "com.apple.sonos-music")
        self.state.updated_at = int(time.time())
        return self.status()

    async def search(self, query: str, count: int = 20) -> dict[str, Any]:
        """Search Apple Music through Sonos."""
        await self._ensure_discovered()
        return await self.sonos_get(
            f"/api/content/v1/households/{self.state.household_id}/services/{self.state.service_id}/accounts/{self.state.account_id}/search?query={quote(query)}&count={count}"
        )

    async def library_tracks(self, offset: int = 0, count: int = 100) -> dict[str, Any]:
        """Browse Apple Music library tracks through Sonos."""
        return await self.library_resources("libraryfolder:f.3", offset, count)

    async def library_resources(self, object_id: str, offset: int = 0, count: int = 100) -> dict[str, Any]:
        """Browse Apple Music library resources through Sonos."""
        await self._ensure_discovered()
        encoded_object_id = quote(object_id, safe="")
        collection = _collection_for_object_id(object_id)
        return await self.sonos_get(
            f"/api/content/v2/households/{self.state.household_id}/services/{self.state.service_id}/accounts/{self.state.account_id}/{collection}/{encoded_object_id}/resources?count={count}&offset={offset}&filterExplicit=false&muse2=true"
        )

    async def sonos_get(self, path: str) -> Any:
        """GET JSON from play.sonos.com with the stored session."""
        url = path if path.startswith("http") else f"{PLAY_SONOS_BASE}{path}"
        response = await self._fetch(url, headers={"Accept": "application/json"})
        body = await _response_json(response)
        if response.status >= 400:
            raise RuntimeError(f"Sonos Web API returned HTTP {response.status}")
        return body

    def needs_refresh(self, threshold_seconds: int) -> bool:
        """Return true when the session is missing or close to expiring."""
        expires_at = self.state.session_expires_at
        return not expires_at or expires_at - int(time.time()) <= threshold_seconds

    def status(self) -> dict[str, Any]:
        """Return non-secret status."""
        return {
            "authenticated": bool(self.state.household_id and self.state.service_id and self.state.account_id),
            "session_expires_at": self.state.session_expires_at,
            "household_present": bool(self.state.household_id),
            "apple_music": {
                "serviceId": self.state.service_id,
                "accountId": self.state.account_id,
                "integrationId": self.state.integration_id,
            },
        }

    async def _ensure_discovered(self) -> None:
        if not self.state.household_id or not self.state.service_id or not self.state.account_id:
            await self.discover()

    async def _nextauth_csrf(self) -> str:
        response = await self._fetch("https://play.sonos.com/api/auth/csrf", headers={"Accept": "application/json"})
        payload = await response.json()
        csrf = payload.get("csrfToken")
        if not csrf:
            raise RuntimeError("Could not get NextAuth CSRF token")
        return str(csrf)

    async def _complete_okta_authn(self, base_url: str, body: dict[str, Any]) -> bool:
        for _ in range(5):
            next_link = body.get("_links", {}).get("next", {})
            href = next_link.get("href")
            method = (next_link.get("hints", {}).get("allow") or ["POST"])[0]
            if body.get("sessionToken"):
                return False
            if body.get("status") != "SUCCESS" or not href or not body.get("stateToken"):
                return False
            response = await self._fetch(
                href,
                method=method,
                headers={"Accept": "application/json", "Content-Type": "application/json", "Origin": base_url},
                json_data={"stateToken": body["stateToken"]} if method != "GET" else None,
            )
            if 300 <= response.status < 400:
                location = response.headers.get("Location")
                if location:
                    await self._follow_redirects(urljoin(href, location))
                    return True
                return False
            body = await _response_json(response)
        return False

    async def _follow_redirects(self, url: str) -> tuple[ClientResponse, str]:
        response = await self._fetch(url)
        for _ in range(30):
            if not 300 <= response.status < 400:
                return response, url
            location = response.headers.get("Location")
            if not location:
                return response, url
            url = urljoin(url, location)
            response = await self._fetch(url)
        return response, url

    async def _fetch(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> ClientResponse:
        request_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            **(headers or {}),
        }
        cookie = self._cookie_header(url)
        if cookie:
            request_headers["Cookie"] = cookie
        response = await self._session.request(method, url, headers=request_headers, data=data, json=json_data, allow_redirects=False)
        self._store_cookies(response, url)
        return response

    def _cookie_header(self, url: str) -> str:
        parsed = URL(url)
        now = int(time.time())
        matching = []
        for cookie in self.state.cookies:
            if cookie.expires and cookie.expires <= now:
                continue
            if parsed.host != cookie.domain and not str(parsed.host).endswith(f".{cookie.domain}"):
                continue
            if not parsed.path.startswith(cookie.path):
                continue
            matching.append(f"{cookie.name}={cookie.value}")
        return "; ".join(matching)

    def _store_cookies(self, response: ClientResponse, url: str) -> None:
        host = str(URL(url).host)
        for name, morsel in response.cookies.items():
            domain = (morsel["domain"] or host).lstrip(".")
            path = morsel["path"] or "/"
            expires = _cookie_expires(morsel["expires"], morsel["max-age"])
            self.state.cookies = [cookie for cookie in self.state.cookies if not (cookie.name == name and cookie.domain == domain and cookie.path == path)]
            if expires == 0:
                continue
            self.state.cookies.append(SonosCookie(name=name, value=morsel.value, domain=domain, path=path, expires=expires))


async def _response_json(response: ClientResponse) -> Any:
    text = await response.text()
    if not text.strip():
        return {}
    return json.loads(text)


def _extract_okta_data(html: str) -> dict[str, str]:
    state_token = _extract_jsonish_value(html, "stateToken")
    redirect_uri = _extract_jsonish_value(html, "redirectUri")
    base_url = _extract_jsonish_value(html, "baseUrl") or "https://login.sonos.com"
    if not state_token or not redirect_uri:
        raise RuntimeError("Could not extract Okta stateToken/redirectUri")
    return {"state_token": state_token, "redirect_uri": redirect_uri, "base_url": base_url}


def _items_from_response(response: Any, collection_key: str) -> list[Any]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        items = response.get("items") or response.get(collection_key)
        if isinstance(items, list):
            return items
    return []


def _collection_for_object_id(object_id: str) -> str:
    if object_id.startswith("libraryartist:"):
        return "artists"
    if object_id.startswith("libraryalbum:"):
        return "albums"
    return "playlists"


def _extract_jsonish_value(text: str, key: str) -> str:
    marker = f'"{key}":"'
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = text.find('"', start)
    return _unescape_js(text[start:end])


def _unescape_js(value: str) -> str:
    return bytes(value.replace("\\x", "\\u00"), "utf-8").decode("unicode_escape")


def _cookie_expires(expires: str, max_age: str) -> int | None:
    if max_age:
        try:
            seconds = int(max_age)
        except ValueError:
            seconds = 0
        return 0 if seconds <= 0 else int(time.time()) + seconds
    if expires:
        try:
            return int(parsedate_to_datetime(expires).timestamp())
        except (TypeError, ValueError, AttributeError):
            _LOGGER.debug("Could not parse cookie expiry %s", expires)
    return None
