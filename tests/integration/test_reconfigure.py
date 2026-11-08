"""Reconfigure via HA's flow manager and reload real platforms, without BLE."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError
from test_coordinator import ADDRESS, snapshot as controller_snapshot

def snapshot():
    data = controller_snapshot()
    return replace(data, device_info=replace(data.device_info, serial="known"))


NEW_ADDRESS = "11:22:33:44:55:66"
THIRD_ADDRESS = "22:33:44:55:66:77"


def add_entry(hass, **kwargs):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}, **kwargs)
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, ADDRESS)}, serial_number="known",
    )
    return entry


async def start(hass, entry):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )


async def submit(hass, result, address=NEW_ADDRESS, confirmed=True):
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: address, "same_controller": confirmed},
    )


def registry_state(hass, entry):
    return {item.unique_id: (item.id, item.entity_id, item.device_id, item.disabled_by)
            for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


async def test_reconfigure_preserves_identity_options_and_unloads(hass):
    entry = add_entry(hass, options={"zone_1_minutes": 3})
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read, patch(
        "custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=snapshot(),
    ) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        before = registry_state(hass, entry)
        device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
        dr.async_get(hass).async_update_device(device.id, area_id=None, name_by_user="My garden")
        for address in (NEW_ADDRESS, THIRD_ADDRESS):
            old_coordinator = entry.runtime_data
            result = await start(hass, entry)
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "reconfigure"
            result = await submit(hass, result, address.upper())
            assert result["reason"] == "reconfigure_successful"
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            assert entry.runtime_data is not old_coordinator
            assert entry.runtime_data.address == address
            assert old_coordinator._unsub_refresh is None
            assert entry.data == {CONF_ADDRESS: address, "identity_address": ADDRESS}
            assert entry.unique_id == ADDRESS
            assert entry.options == {"zone_1_minutes": 3}
            assert registry_state(hass, entry) == before
            devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
            assert [item.id for item in devices] == [device.id]
            assert devices[0].identifiers == {(DOMAIN, ADDRESS)}
            assert devices[0].name_by_user == "My garden"
            validate.assert_awaited_with(hass, address)
            read.assert_awaited_with(hass, address)
        assert await hass.config_entries.async_unload(entry.entry_id)
        count = read.await_count
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()
        assert read.await_count == count


@pytest.mark.parametrize(("error", "expected"), [
    (AuthenticationError(), "invalid_auth"), (ConnectivityError(), "cannot_connect"),
    (TimeoutError(), "cannot_connect"), (InvalidResponseError(), "invalid_response"),
])
async def test_errors_retry(hass, error, expected):
    entry = add_entry(hass)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", side_effect=error):
        result = await submit(hass, await start(hass, entry))
    assert result["errors"] == {"base": expected}
    assert entry.data == {CONF_ADDRESS: ADDRESS}
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.async_setup_entry", return_value=True,
    ):
        result = await submit(hass, result)
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(("address", "confirmed", "expected"), [
    ("invalid", True, "invalid_address"), (NEW_ADDRESS, False, "confirm_controller"),
])
async def test_input_errors(hass, address, confirmed, expected):
    entry = add_entry(hass)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device") as validate:
        result = await submit(hass, await start(hass, entry), address, confirmed)
    assert result["errors"] == {"base": expected}
    validate.assert_not_called()
    assert entry.data == {CONF_ADDRESS: ADDRESS}


@pytest.mark.parametrize("historical", [False, True])
async def test_collision(hass, historical):
    entry = add_entry(hass)
    MockConfigEntry(domain=DOMAIN, unique_id=NEW_ADDRESS, data={
        CONF_ADDRESS: THIRD_ADDRESS if historical else NEW_ADDRESS,
        "identity_address": NEW_ADDRESS,
    }).add_to_hass(hass)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device") as validate:
        result = await submit(hass, await start(hass, entry))
    assert result["reason"] == "already_configured"
    validate.assert_not_called()
    assert entry.data == {CONF_ADDRESS: ADDRESS}


@pytest.mark.parametrize("serial", [None, "different", "known"])
async def test_known_serial(hass, serial):
    entry = add_entry(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, ADDRESS)}, serial_number="known",
    )
    data = snapshot()
    data = replace(data, device_info=replace(data.device_info, serial=serial))
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=data), patch(
        "custom_components.solem_woobee.async_setup_entry", return_value=True,
    ):
        result = await submit(hass, await start(hass, entry))
        await hass.async_block_till_done()
    if serial == "known":
        assert result["reason"] == "reconfigure_successful"
    else:
        assert result["errors"] == {"base": "wrong_controller"}
        assert entry.data == {CONF_ADDRESS: ADDRESS}


async def test_collision_appears_during_validation(hass):
    entry = add_entry(hass)

    async def validate(*args):
        MockConfigEntry(domain=DOMAIN, unique_id=NEW_ADDRESS,
                        data={CONF_ADDRESS: NEW_ADDRESS}).add_to_hass(hass)
        return snapshot()

    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", side_effect=validate):
        result = await submit(hass, await start(hass, entry))
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_ADDRESS: ADDRESS}


async def test_cancel(hass):
    entry = add_entry(hass)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device") as validate:
        result = await start(hass, entry)
        hass.config_entries.flow.async_abort(result["flow_id"])
    validate.assert_not_called()
    assert entry.data == {CONF_ADDRESS: ADDRESS}


async def test_unknown_original_identity_fails_closed(hass):
    entry = add_entry(hass)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    dr.async_get(hass).async_update_device(device.id, serial_number=None)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=snapshot()):
        result = await submit(hass, await start(hass, entry))
    assert result["errors"] == {"base": "identity_unavailable"}
    assert entry.data == {CONF_ADDRESS: ADDRESS}
