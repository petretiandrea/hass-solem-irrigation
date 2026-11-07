"""Entry lifecycle and transient resource ownership."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee import async_setup_entry, async_unload_entry
from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.connection import async_validate_device
from custom_components.solem_woobee.woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError

ADDRESS = "aa:bb:cc:dd:ee:ff"


async def test_setup_unload_reload(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.async_validate_device", return_value=object()) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert validate.call_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(("error", "expected"), [
    (ConnectivityError(), ConfigEntryNotReady),
    (AuthenticationError(), ConfigEntryError),
    (InvalidResponseError(), ConfigEntryError),
])
async def test_setup_errors(hass, error, expected):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    with patch("custom_components.solem_woobee.async_validate_device", side_effect=error):
        with pytest.raises(expected):
            await async_setup_entry(hass, entry)


@pytest.mark.parametrize("failure", [None, ConnectivityError(), AuthenticationError()])
async def test_probe_closes_session(hass, failure):
    client = AsyncMock()
    client.read_device_info.side_effect = failure
    scope = AsyncMock()
    scope.__aenter__.return_value = client
    with patch("homeassistant.components.bluetooth.async_ble_device_from_address", return_value=object()), patch(
        "custom_components.solem_woobee.connection.WooBeeConnection", return_value=scope,
    ):
        if failure:
            with pytest.raises(type(failure)):
                await async_validate_device(hass, ADDRESS)
        else:
            await async_validate_device(hass, ADDRESS)
    scope.__aexit__.assert_awaited_once()


async def test_unreachable_and_bluetooth_address_case(hass):
    with patch("homeassistant.components.bluetooth.async_ble_device_from_address", return_value=None) as lookup:
        with pytest.raises(ConnectivityError):
            await async_validate_device(hass, ADDRESS)
    lookup.assert_called_once_with(hass, ADDRESS.upper(), connectable=True)
