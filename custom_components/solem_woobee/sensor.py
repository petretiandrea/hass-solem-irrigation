"""Read-only values from the shared WB-4 snapshot."""
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WooBeeCoordinator
from .data import WooBeeConfigEntry
from .entity import WooBeeEntity, WooBeeZoneEntity
from .woobee_api import ControllerIdentity

PARALLEL_UPDATES = 0

REMAINING = SensorEntityDescription(
    key="remaining_time", translation_key="remaining_time",
    device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.SECONDS,
)
BATTERY_RAW = SensorEntityDescription(
    key="battery_raw", translation_key="battery_raw",
    entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
)

RSSI = SensorEntityDescription(
    key="rssi", translation_key="rssi", entity_category=EntityCategory.DIAGNOSTIC,
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    state_class=SensorStateClass.MEASUREMENT,
)
LAST_FETCHED = SensorEntityDescription(
    key="last_fetched", translation_key="last_fetched",
    entity_category=EntityCategory.DIAGNOSTIC, device_class=SensorDeviceClass.TIMESTAMP,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: WooBeeConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    """Subscribe entities to one coordinator; never perform per-entity BLE reads."""
    async_add_entities([
        WooBeeBatteryRawSensor(entry.runtime_data),
        WooBeeRssiSensor(entry.runtime_data),
        WooBeeLastFetchedSensor(entry.runtime_data),
        *(WooBeeRemainingSensor(entry.runtime_data, zone) for zone in range(1, 5)),
    ])


class WooBeeRemainingSensor(WooBeeZoneEntity, SensorEntity):
    """Reported remaining duration, preserving absent pages as unknown."""

    entity_description = REMAINING

    def __init__(self, coordinator: WooBeeCoordinator, zone: int) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).zones[zone - 1].unique_id}_remaining_time"
        self._attr_translation_placeholders = {"zone": str(zone)}

    @property
    def native_value(self) -> int | None:
        return self.remaining_seconds


class WooBeeBatteryRawSensor(WooBeeEntity, SensorEntity):
    """Unscaled protocol byte; neither percentage nor voltage is established."""

    entity_description = BATTERY_RAW

    def __init__(self, coordinator: WooBeeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).unique_id}_battery_raw"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.state.status.battery_raw


class WooBeeRssiSensor(WooBeeEntity, SensorEntity):
    """Latest connectable Bluetooth advertisement RSSI, sampled at poll time."""

    entity_description = RSSI

    def __init__(self, coordinator: WooBeeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).unique_id}_rssi"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.rssi


class WooBeeLastFetchedSensor(WooBeeEntity, SensorEntity):
    """Completion time of the most recent successful full poll."""

    entity_description = LAST_FETCHED

    def __init__(self, coordinator: WooBeeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{ControllerIdentity(coordinator.identity_address).unique_id}_last_fetched"

    @property
    def available(self) -> bool:
        # Retain freshness evidence during outages, like the connectivity entity.
        return self.coordinator.data is not None

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.last_fetched
