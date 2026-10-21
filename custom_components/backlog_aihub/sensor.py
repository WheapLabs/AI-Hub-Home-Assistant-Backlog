"""« To process » sensor: what waits for the agents in the hub's Backlog."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BacklogConfigEntry
from .const import DOMAIN
from .coordinator import BacklogCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: BacklogConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ToProcessSensor(entry.runtime_data, entry)])


class ToProcessSensor(CoordinatorEntity[BacklogCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "a_traiter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BacklogCoordinator, entry: BacklogConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_a_traiter"
        parts = urlsplit(coordinator.client.url)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Backlog AI Hub",
            manufacturer="AI Hub",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{parts.scheme}://{parts.netloc}/",
        )

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("pour_les_agents")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = dict(self.coordinator.data or {})
        data.pop("pour_les_agents", None)
        return data
