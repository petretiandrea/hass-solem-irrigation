"""Entry lifecycle and transient resource ownership."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee import async_setup_entry, async_unload_entry
from test_coordinator import snapshot
from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.connection import async_validate_device
from custom_components.solem_woobee.woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError

ADDRESS = "aa:bb:cc:dd:ee:ff"


async def test_setup_unload_reload(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert validate.call_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("error", [ConnectivityError(), AuthenticationError(), InvalidResponseError()])
async def test_setup_errors(hass, error):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", side_effect=error):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


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


@pytest.mark.parametrize("offline", [False, True])
async def test_fixed_controller_entry_removal(hass, offline):
    """Unavailability retains the device; removing its entry cleans all entities."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        devices = dr.async_get(hass)
        entities = er.async_get(hass)
        registered = dr.async_entries_for_config_entry(devices, entry.entry_id)
        assert len(registered) == 1
        device_id = registered[0].id
        assert len(er.async_entries_for_config_entry(entities, entry.entry_id)) == 25
        if offline:
            read.side_effect = ConnectivityError()
            await entry.runtime_data.async_refresh()
            assert devices.async_get(device_id) is not None
            assert not ir.async_get(hass).issues
            read.side_effect = None
            await entry.runtime_data.async_refresh()
            assert entry.runtime_data.last_update_success
            assert devices.async_get(device_id) is not None
            read.side_effect = ConnectivityError()
            await coordinator.async_refresh()
        assert not ir.async_get(hass).issues
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert devices.async_get(device_id) is None
        assert not er.async_entries_for_config_entry(entities, entry.entry_id)
        assert not coordinator._listeners
        assert coordinator._unsub_refresh is None
