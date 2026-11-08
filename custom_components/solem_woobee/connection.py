"""HA Bluetooth adapter for short, authenticated read sessions."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .data import WooBeeData
from .woobee_api import ConnectivityError, SolemSession, WOOBEE_V2_GATT, WooBeeV2


@asynccontextmanager
async def connection_scope(hass: HomeAssistant, address: str) -> AsyncIterator[WooBeeV2]:
    """Resolve the current connectable BLE device for a fresh session."""
    lookup_address = address.upper() if len(address) == 17 else address
    device = bluetooth.async_ble_device_from_address(hass, lookup_address, connectable=True)
    if device is None:
        raise ConnectivityError("Device is not reachable through Home Assistant Bluetooth")
    try:
        client = await establish_connection(
            BleakClientWithServiceCache, device, address,
            ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                hass, lookup_address, connectable=True,
            ) or device,
        )
    except (BleakError, OSError, TimeoutError) as exc:
        raise ConnectivityError("BLE connection failed") from exc
    # The connector owns establishment/retries; the session owns cleanup. Do not
    # call connect again or impose the standalone client's ten-second deadline.
    async with SolemSession(client, WOOBEE_V2_GATT, owns_connection=True,
                            already_connected=True) as session:
        yield WooBeeV2(session)


async def async_validate_device(hass: HomeAssistant, address: str) -> WooBeeData:
    """Authenticate and read identity/state, then release all BLE resources."""
    async with connection_scope(hass, address) as client:
        info = await client.read_device_info()
        state = await client.read_state()
    return WooBeeData(address, info, state)
