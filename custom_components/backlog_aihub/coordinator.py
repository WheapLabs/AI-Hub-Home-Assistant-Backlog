"""Reads the hub's Backlog every few minutes for the sensor (no copy is written anywhere)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BacklogClient, CannotConnect, InvalidAuth, Refused
from .const import DOMAIN, SCAN_INTERVAL
from .summary import summarize

_LOGGER = logging.getLogger(__name__)


class BacklogCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data = the counts of summarize() plus « rev » (the hub's revision)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: BacklogClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snap = await self.client.snapshot()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (CannotConnect, Refused) as err:
            raise UpdateFailed(str(err)) from err
        return {**summarize(snap.data), "rev": snap.rev}
