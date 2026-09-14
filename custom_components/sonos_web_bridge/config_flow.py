"""Config flow for Sonos Web Bridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_PSONO_BEARER_TOKEN,
    CONF_PSONO_BEARER_TOKEN_FILE,
    CONF_PSONO_MCP_URL,
    CONF_REFRESH_INTERVAL_HOURS,
    CONF_REFRESH_THRESHOLD_HOURS,
    CONF_SONOS_EMAIL_KEY,
    CONF_SONOS_PASSWORD_KEY,
    DEFAULT_PSONO_MCP_URL,
    DEFAULT_REFRESH_INTERVAL_HOURS,
    DEFAULT_REFRESH_THRESHOLD_HOURS,
    DEFAULT_SONOS_EMAIL_KEY,
    DEFAULT_SONOS_PASSWORD_KEY,
    DOMAIN,
)


class SonosWebBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonos Web Bridge."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Create the integration entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Sonos Web Bridge", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_PSONO_MCP_URL, default=DEFAULT_PSONO_MCP_URL): str,
                vol.Optional(CONF_PSONO_BEARER_TOKEN, default=""): str,
                vol.Optional(CONF_PSONO_BEARER_TOKEN_FILE, default=""): str,
                vol.Required(CONF_SONOS_EMAIL_KEY, default=DEFAULT_SONOS_EMAIL_KEY): str,
                vol.Required(CONF_SONOS_PASSWORD_KEY, default=DEFAULT_SONOS_PASSWORD_KEY): str,
                vol.Required(CONF_REFRESH_INTERVAL_HOURS, default=DEFAULT_REFRESH_INTERVAL_HOURS): int,
                vol.Required(CONF_REFRESH_THRESHOLD_HOURS, default=DEFAULT_REFRESH_THRESHOLD_HOURS): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

