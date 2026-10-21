"""Backlog AI Hub: Home Assistant actions that write to the AI Hub's Backlog.

The integration keeps no copy of the Backlog: every action is relayed to the
hub (POST /backlog-api/service) and the hub's answer is returned as the
action's response. A sensor polls the hub (GET /backlog-api/donnees, 304 when
nothing changed) to show what is waiting.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import BacklogClient, CannotConnect, InvalidAuth, Refused
from .const import CONF_CA_CERT, DOMAIN, EXPORT_ACTION, WRITE_ACTIONS
from .coordinator import BacklogCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The hub checks every field (same rules as its command line): here we only make sure it is an object.
WRITE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)
EXPORT_SCHEMA = vol.Schema({})

type BacklogConfigEntry = ConfigEntry[BacklogCoordinator]


def ssl_setting(data: dict[str, Any]) -> ssl.SSLContext | bool | None:
    """TLS setting of the entry. Blocking (reads the CA file): call it in the executor."""
    if not data.get(CONF_VERIFY_SSL, True):
        return False
    if data.get(CONF_CA_CERT):
        return ssl.create_default_context(cafile=data[CONF_CA_CERT])
    return None


async def async_client(hass: HomeAssistant, data: dict[str, Any]) -> BacklogClient:
    """Client for the settings of an entry (or of the setup form)."""
    try:
        ssl_context = await hass.async_add_executor_job(ssl_setting, data)
    except (OSError, ssl.SSLError) as err:
        raise CannotConnect(f"CA certificate: {err}") from err
    return BacklogClient(async_get_clientsession(hass), data[CONF_URL], data[CONF_API_TOKEN], ssl_context)


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Plain JSON (dates from the UI selectors become text)."""
    return json.loads(json.dumps(data, default=str))


def _loaded_entry(hass: HomeAssistant) -> BacklogConfigEntry:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")


async def _call(hass: HomeAssistant, action: str, data: dict[str, Any]) -> dict[str, Any]:
    entry = _loaded_entry(hass)
    coordinator = entry.runtime_data
    try:
        out = await coordinator.client.service(action, _clean(data))
    except Refused as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="refused", translation_placeholders={"message": str(err)}
        ) from err
    except InvalidAuth as err:
        entry.async_start_reauth(hass)
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_auth") from err
    except CannotConnect as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cannot_connect", translation_placeholders={"message": str(err)}
        ) from err
    if action != EXPORT_ACTION:
        await coordinator.async_request_refresh()
    return out


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registers the actions once (they answer « not loaded » while no entry is set up)."""

    def write_handler(action: str):
        async def handler(call: ServiceCall) -> ServiceResponse:
            out = await _call(hass, action, dict(call.data))
            return {"rev": out["rev"], "reponse": out.get("reponse")}

        return handler

    async def export_handler(call: ServiceCall) -> ServiceResponse:
        out = await _call(hass, EXPORT_ACTION, {})
        return out.get("reponse") or {}

    for action in WRITE_ACTIONS:
        hass.services.async_register(
            DOMAIN, action, write_handler(action), schema=WRITE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
        )
    hass.services.async_register(
        DOMAIN, EXPORT_ACTION, export_handler, schema=EXPORT_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BacklogConfigEntry) -> bool:
    client = await async_client(hass, dict(entry.data))
    coordinator = BacklogCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BacklogConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
