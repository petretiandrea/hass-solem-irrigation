"""Momentary manual irrigation commands; stop is controller-wide."""
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WooBeeCoordinator
from .data import WooBeeConfigEntry
from .entity import WooBeeEntity
from .woobee_api import ControllerIdentity

PARALLEL_UPDATES = 0  # Coordinator serializes all controller BLE sessions.


async def async_setup_entry(
    hass: HomeAssistant, entry: WooBeeConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WooBeeStopButton(entry.runtime_data)])


class WooBeeStopButton(WooBeeEntity, ButtonEntity):
    """Never label the recovered global stop as a per-zone operation."""

    _attr_translation_key = "stop_all"

    def __init__(self, coordinator: WooBeeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).unique_id}_stop_all"

    async def async_press(self) -> None:
        await self.coordinator.async_irrigate(None)
