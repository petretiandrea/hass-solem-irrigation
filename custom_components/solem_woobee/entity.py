"""Shared availability and controller association for future platforms."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WooBeeCoordinator
from .data import WooBeeData
from .woobee_api import ControllerIdentity


def controller_device_info(data: WooBeeData) -> DeviceInfo:
    """Use configured BLE identity even when optional identity pages are absent."""
    return DeviceInfo(
        identifiers={(DOMAIN, ControllerIdentity(data.address).unique_id)},
        manufacturer="SOLEM",
        model="WooBee WB-4",
        name=data.device_info.name or "SOLEM WooBee",
        sw_version=data.device_info.firmware,
        hw_version=data.device_info.hardware,
        serial_number=data.device_info.serial,
    )


class WooBeeEntity(CoordinatorEntity[WooBeeCoordinator]):
    """Controller entities share coordinator availability and registry device."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return controller_device_info(self.coordinator.data)


class WooBeeZoneEntity(WooBeeEntity):
    """A zone belongs to its controller; absent duration is not zero."""

    def __init__(self, coordinator: WooBeeCoordinator, zone: int) -> None:
        super().__init__(coordinator)
        identity = ControllerIdentity(coordinator.address)
        if type(zone) is not int or not 1 <= zone <= 4:
            raise ValueError("zone must be an integer from 1 to 4")
        self.zone = zone
        self._attr_unique_id = identity.zones[zone - 1].unique_id

    @property
    def remaining_seconds(self) -> int | None:
        """Return an unknown value for a missing page, keeping the zone reachable."""
        return self.coordinator.data.state.status.zone_remaining_seconds[self.zone - 1]
