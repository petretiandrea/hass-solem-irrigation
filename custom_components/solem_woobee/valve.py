"""Timed water valves with controller-reported state and guarded global stop."""
from typing import Any

from homeassistant.components.valve import ValveDeviceClass, ValveEntity, ValveEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import WooBeeConfigEntry
from .entity import WooBeeZoneEntity
from .services import valid_minutes

PARALLEL_UPDATES = 0  # The coordinator serializes reads and commands.
DURATION_OPTIONS = "zone_duration_minutes"


async def async_setup_entry(
    hass: HomeAssistant, entry: WooBeeConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WooBeeValve(entry, zone) for zone in range(1, 5)])


class WooBeeValve(WooBeeZoneEntity, ValveEntity):
    """Opening is timed; closing never intentionally stops another zone."""

    _attr_translation_key = "zone"
    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(self, entry: WooBeeConfigEntry, zone: int) -> None:
        super().__init__(entry.runtime_data, zone)
        self._entry = entry
        self._attr_translation_placeholders = {"zone": str(zone)}

    @property
    def is_closed(self) -> bool:
        return self.coordinator.data.state.status.active_zone != self.zone

    @property
    def default_duration_minutes(self) -> int:
        """Persist the user's local default, independently for each zone."""
        return self._entry.options.get(DURATION_OPTIONS, {}).get(str(self.zone), 1)

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"default_duration_minutes": self.default_duration_minutes}

    async def async_open_valve(self, **kwargs: Any) -> None:
        await self.async_start_irrigation(self.default_duration_minutes)

    async def async_close_valve(self, **kwargs: Any) -> None:
        await self.coordinator.async_irrigate(self.zone, close_zone=True)

    async def async_start_irrigation(self, minutes: int) -> None:
        """Override duration for this run without modifying the default."""
        await self.coordinator.async_irrigate(self.zone, valid_minutes(minutes))

    async def async_set_default_duration(self, minutes: int) -> None:
        """Store HA's duration preference without writing controller programs."""
        durations = {**self._entry.options.get(DURATION_OPTIONS, {}),
                     str(self.zone): valid_minutes(minutes)}
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, DURATION_OPTIONS: durations},
        )
        self.async_write_ha_state()
