"""Reported controller flags and zone state, with explicit read connectivity."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WooBeeCoordinator
from .data import WooBeeConfigEntry
from .entity import WooBeeEntity, WooBeeZoneEntity
from .woobee_api import ControllerIdentity

PARALLEL_UPDATES = 0

CONTROLLER = (
    BinarySensorEntityDescription(key="connectivity", translation_key="connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=EntityCategory.DIAGNOSTIC),
    BinarySensorEntityDescription(key="enabled", translation_key="enabled"),
    BinarySensorEntityDescription(key="manual", translation_key="manual"),
    BinarySensorEntityDescription(key="sensor_open", translation_key="sensor_open",
        entity_category=EntityCategory.DIAGNOSTIC),
    BinarySensorEntityDescription(key="clock_alarm", translation_key="clock_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM, entity_category=EntityCategory.DIAGNOSTIC),
)
ZONE = (
    BinarySensorEntityDescription(key="irrigating", translation_key="irrigating",
        device_class=BinarySensorDeviceClass.RUNNING),
    BinarySensorEntityDescription(key="valve_fault", translation_key="valve_fault",
        device_class=BinarySensorDeviceClass.PROBLEM, entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: WooBeeConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose only fields whose meaning is established by the client."""
    async_add_entities([
        *(WooBeeControllerBinarySensor(entry.runtime_data, description) for description in CONTROLLER),
        *(WooBeeZoneBinarySensor(entry.runtime_data, zone, description)
          for zone in range(1, 5) for description in ZONE),
    ])


class WooBeeControllerBinarySensor(WooBeeEntity, BinarySensorEntity):
    """Connectivity describes the last completed read, not a persistent BLE link."""

    def __init__(self, coordinator: WooBeeCoordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).unique_id}_{description.key}"

    @property
    def available(self) -> bool:
        return self.entity_description.key == "connectivity" or super().available

    @property
    def is_on(self) -> bool:
        if self.entity_description.key == "connectivity":
            return self.coordinator.last_update_success
        return getattr(self.coordinator.data.state.status, self.entity_description.key)


class WooBeeZoneBinarySensor(WooBeeZoneEntity, BinarySensorEntity):
    """Controller-reported activity and electrical fault; no inferred water flow."""

    def __init__(self, coordinator: WooBeeCoordinator, zone: int,
                 description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, zone)
        self.entity_description = description
        self._attr_unique_id += f"_{description.key}"
        self._attr_translation_placeholders = {"zone": str(zone)}

    @property
    def is_on(self) -> bool:
        if self.entity_description.key == "irrigating":
            return self.coordinator.data.state.status.active_zone == self.zone
        return self.zone in self.coordinator.data.state.valve_faults.faulty_zones
