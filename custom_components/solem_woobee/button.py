"""Momentary manual irrigation commands; stop is controller-wide."""
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WooBeeCoordinator
from .data import WooBeeConfigEntry
from .entity import WooBeeEntity, WooBeeZoneEntity
from .services import valid_minutes
from .woobee_api import ControllerIdentity

PARALLEL_UPDATES = 0  # Coordinator serializes all controller BLE sessions.


async def async_setup_entry(
    hass: HomeAssistant, entry: WooBeeConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([
        *(WooBeeStartButton(entry.runtime_data, zone) for zone in range(1, 5)),
        WooBeeStopButton(entry.runtime_data),
    ])


class WooBeeStartButton(WooBeeZoneEntity, ButtonEntity):
    """Start a timed run; press uses one minute, entity action accepts duration."""

    _attr_translation_key = "start_zone"
    _attr_supported_features = 1

    def __init__(self, coordinator: WooBeeCoordinator, zone: int) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id += "_start"
        self._attr_translation_placeholders = {"zone": str(zone)}

    async def async_press(self) -> None:
        await self.async_start_irrigation(1)

    async def async_start_irrigation(self, minutes: int) -> None:
        await self.coordinator.async_irrigate(self.zone, valid_minutes(minutes))


class WooBeeStopButton(WooBeeEntity, ButtonEntity):
    """Never label the recovered global stop as a per-zone operation."""

    _attr_translation_key = "stop_all"

    def __init__(self, coordinator: WooBeeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.address).unique_id}_stop_all"

    async def async_press(self) -> None:
        await self.coordinator.async_irrigate(None)
