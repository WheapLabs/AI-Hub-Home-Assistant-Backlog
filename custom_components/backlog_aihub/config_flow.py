"""Setup from the UI: the hub's address and its Backlog token, checked before the entry is created."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from . import async_client
from .api import CannotConnect, InvalidAuth, Refused, normalize_url
from .const import CONF_CA_CERT, DOMAIN


def _schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Required(CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
            vol.Optional(CONF_CA_CERT, default=defaults.get(CONF_CA_CERT, "")): str,
        }
    )


class BacklogAIHubConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        """Returns (cleaned settings, errors)."""
        data = {**data, CONF_CA_CERT: (data.get(CONF_CA_CERT) or "").strip(), CONF_API_TOKEN: data[CONF_API_TOKEN].strip()}
        try:
            data[CONF_URL] = normalize_url(data[CONF_URL])
        except ValueError:
            return data, {CONF_URL: "invalid_url"}
        try:
            client = await async_client(self.hass, data)
            await client.validate()
        except InvalidAuth:
            return data, {CONF_API_TOKEN: "invalid_auth"}
        except (CannotConnect, Refused):
            return data, {"base": "cannot_connect"}
        return data, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._check(user_input)
            if not errors:
                return self.async_create_entry(title="Backlog AI Hub", data=data)
            user_input = data
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._check(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
            user_input = data
        return self.async_show_form(
            step_id="reconfigure", data_schema=_schema(user_input or entry.data), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._check({**entry.data, CONF_API_TOKEN: user_input[CONF_API_TOKEN]})
            if errors and CONF_API_TOKEN not in errors:
                errors = {"base": "cannot_connect"}
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
            ),
            errors=errors,
        )
