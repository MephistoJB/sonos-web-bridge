"""Config flow for Sonos Web Bridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

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

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SonosWebBridgeOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Create the integration entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Sonos Web Bridge", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_SONOS_EMAIL): str,
                vol.Required(CONF_SONOS_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_REFRESH_INTERVAL_HOURS, default=DEFAULT_REFRESH_INTERVAL_HOURS): int,
                vol.Required(CONF_REFRESH_THRESHOLD_HOURS, default=DEFAULT_REFRESH_THRESHOLD_HOURS): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)


class SonosWebBridgeOptionsFlow(config_entries.OptionsFlow):
    """Handle Sonos Web Bridge options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Update Sonos credentials and refresh settings."""
        if user_input is not None:
            current = {**self._config_entry.data, **self._config_entry.options}
            if not user_input.get(CONF_SONOS_PASSWORD):
                user_input[CONF_SONOS_PASSWORD] = current.get(CONF_SONOS_PASSWORD, "")
            if not user_input.get(CONF_PSONO_BEARER_TOKEN):
                user_input[CONF_PSONO_BEARER_TOKEN] = current.get(CONF_PSONO_BEARER_TOKEN, "")
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_SONOS_EMAIL, default=current.get(CONF_SONOS_EMAIL, "")): str,
                vol.Required(CONF_SONOS_PASSWORD, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_REFRESH_INTERVAL_HOURS,
                    default=current.get(CONF_REFRESH_INTERVAL_HOURS, DEFAULT_REFRESH_INTERVAL_HOURS),
                ): int,
                vol.Required(
                    CONF_REFRESH_THRESHOLD_HOURS,
                    default=current.get(CONF_REFRESH_THRESHOLD_HOURS, DEFAULT_REFRESH_THRESHOLD_HOURS),
                ): int,
                vol.Optional(CONF_PSONO_MCP_URL, default=current.get(CONF_PSONO_MCP_URL, DEFAULT_PSONO_MCP_URL)): str,
                vol.Optional(CONF_PSONO_BEARER_TOKEN, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_PSONO_BEARER_TOKEN_FILE, default=current.get(CONF_PSONO_BEARER_TOKEN_FILE, "")): str,
                vol.Optional(CONF_SONOS_EMAIL_KEY, default=current.get(CONF_SONOS_EMAIL_KEY, DEFAULT_SONOS_EMAIL_KEY)): str,
                vol.Optional(
                    CONF_SONOS_PASSWORD_KEY,
                    default=current.get(CONF_SONOS_PASSWORD_KEY, DEFAULT_SONOS_PASSWORD_KEY),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
