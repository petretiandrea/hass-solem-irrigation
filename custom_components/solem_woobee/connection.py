"""HA Bluetooth adapter for short, authenticated read sessions."""
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from bleak import BleakClient

from .data import WooBeeData
from .woobee_api import ConnectivityError, WooBeeConnection


def connection_scope(hass: HomeAssistant, address: str) -> WooBeeConnection:
    """Resolve the current connectable BLE device for a fresh session."""
    lookup_address = address.upper() if len(address) == 17 else address
    device = bluetooth.async_ble_device_from_address(hass, lookup_address, connectable=True)
    if device is None:
        raise ConnectivityError("Device is not reachable through Home Assistant Bluetooth")
    return WooBeeConnection(address, lambda _: BleakClient(device))


async def async_validate_device(hass: HomeAssistant, address: str) -> WooBeeData:
    """Authenticate and read identity/state, then release all BLE resources."""
    async with connection_scope(hass, address) as client:
        info = await client.read_device_info()
        state = await client.read_state()
    return WooBeeData(address, info, state)
