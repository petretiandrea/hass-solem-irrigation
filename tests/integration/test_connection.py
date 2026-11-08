"""HA connector establishment, ownership and recovery without physical BLE."""
import asyncio
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache
import pytest

from custom_components.solem_woobee.connection import connection_scope
from custom_components.solem_woobee.woobee_api import ConnectivityError, InvalidResponseError

ADDRESS = "aa:bb:cc:dd:ee:ff"
MODULE = "custom_components.solem_woobee.connection"


def transport():
    client = AsyncMock()
    callbacks = {}
    client.read_gatt_char.return_value = bytes(range(16))

    async def subscribe(uuid, callback):
        callbacks[uuid] = callback

    async def write(uuid, data, *, response):
        callbacks[uuid](None, bytearray(b"AUTHENTICATED\x00"))

    client.start_notify.side_effect = subscribe
    client.write_gatt_char.side_effect = write
    return client


@pytest.mark.parametrize("address", [ADDRESS, "synthetic-device-uuid"])
@pytest.mark.parametrize("outcome", [None, InvalidResponseError, asyncio.CancelledError])
async def test_connected_session_cleanup(hass, address, outcome):
    client = transport()
    device, refreshed = object(), object()
    with patch(f"{MODULE}.bluetooth.async_ble_device_from_address", return_value=device) as lookup, patch(
        f"{MODULE}.establish_connection", return_value=client,
    ) as establish:
        async def operate():
            async with connection_scope(hass, address):
                if outcome:
                    raise outcome()
        if outcome:
            with pytest.raises(outcome):
                await operate()
        else:
            await operate()
        args, kwargs = establish.call_args
        assert args == (BleakClientWithServiceCache, device, address)
        lookup.assert_called_once_with(hass, address.upper() if address == ADDRESS else address,
                                       connectable=True)
        lookup.return_value = refreshed
        assert kwargs["ble_device_callback"]() is refreshed
        lookup.return_value = None
        assert kwargs["ble_device_callback"]() is device
    client.connect.assert_not_awaited()
    client.disconnect.assert_awaited_once()
    assert client.stop_notify.await_count == 2


@pytest.mark.parametrize("error", [BleakError("offline"), OSError("offline"), TimeoutError()])
async def test_establishment_error_is_recoverable(hass, error):
    with patch(f"{MODULE}.bluetooth.async_ble_device_from_address", return_value=object()), patch(
        f"{MODULE}.establish_connection", side_effect=error,
    ) as establish:
        with pytest.raises(ConnectivityError) as raised:
            async with connection_scope(hass, ADDRESS):
                pytest.fail("must not enter a failed connection")
        assert raised.value.__cause__ is error
        assert establish.await_count == 1
        establish.side_effect = None
        establish.return_value = transport()
        async with connection_scope(hass, ADDRESS):
            pass
        establish.return_value.disconnect.assert_awaited_once()


async def test_authentication_failure_releases_connected_client(hass):
    client = transport()
    client.read_gatt_char.return_value = b"invalid challenge"
    with patch(f"{MODULE}.bluetooth.async_ble_device_from_address", return_value=object()), patch(
        f"{MODULE}.establish_connection", return_value=client,
    ) as establish:
        with pytest.raises(InvalidResponseError):
            async with connection_scope(hass, ADDRESS):
                pytest.fail("must not enter an unauthenticated session")
    establish.assert_awaited_once()
    client.connect.assert_not_awaited()
    client.disconnect.assert_awaited_once()


async def test_connection_cancellation_propagates(hass):
    with patch(f"{MODULE}.bluetooth.async_ble_device_from_address", return_value=object()), patch(
        f"{MODULE}.establish_connection", side_effect=asyncio.CancelledError,
    ):
        with pytest.raises(asyncio.CancelledError):
            async with connection_scope(hass, ADDRESS):
                pytest.fail("must not enter a cancelled connection")
