"""Shared snapshots, partial data, recovery and registry ownership."""
from unittest.mock import patch
from dataclasses import replace
from datetime import timedelta
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee import async_unload_entry
from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.coordinator import WooBeeCoordinator
from custom_components.solem_woobee.data import WooBeeData
from custom_components.solem_woobee.entity import WooBeeEntity, WooBeeZoneEntity
from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError,
    WooBeeDeviceInfo, WooBeeState, WooBeeStatus, WooBeeValveFaults, WooBeeInputAlerts,
)

ADDRESS = "aa:bb:cc:dd:ee:ff"


def snapshot():
    return WooBeeData(ADDRESS,
        WooBeeDeviceInfo("Garden", None, None, "7.0.2", None, None, (), ()),
        WooBeeState(WooBeeStatus(True, False, False, False, None, 90, 0, None,
            None, (0, 0, None, None), ()),
            WooBeeValveFaults((), b""), WooBeeInputAlerts(())))


@pytest.mark.parametrize("error", [ConnectivityError(), AuthenticationError(), InvalidResponseError(), TimeoutError()])
async def test_update_failure_and_recovery(hass, error):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device",
               side_effect=[snapshot(), error, snapshot()]) as read:
        await coordinator.async_refresh()
        entities = [WooBeeEntity(coordinator), WooBeeZoneEntity(coordinator, 1)]
        assert all(entity.available for entity in entities)
        assert not WooBeeZoneEntity(coordinator, 3).available
        previous = coordinator.data
        await coordinator.async_refresh()
        assert coordinator.data is previous
        assert not any(entity.available for entity in entities)
        await coordinator.async_refresh()
        assert all(entity.available for entity in entities)
        assert read.await_count == 3
    await coordinator.async_shutdown()


async def test_registry_shared_and_unload(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        zone = WooBeeZoneEntity(coordinator, 2)
        device, = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        assert device is not None
        assert zone.device_info["identifiers"] == device.identifiers
        assert zone.unique_id == ADDRESS + "_zone_2"
        assert read.await_count == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_scheduled_poll_stops_after_unload(hass, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert read.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert read.await_count == 2


async def test_failed_platform_unload_preserves_polling(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=False), patch.object(
            entry.runtime_data, "async_shutdown"
        ) as shutdown:
            assert not await async_unload_entry(hass, entry)
            shutdown.assert_not_called()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_optional_identity_and_disabled_controller(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS.upper()})
    coordinator = WooBeeCoordinator(hass, entry)
    data = snapshot()
    data = replace(data,
        device_info=replace(data.device_info, name=None, firmware=None),
        state=replace(data.state, status=replace(data.state.status, enabled=False)))
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=data):
        await coordinator.async_refresh()
    entity = WooBeeZoneEntity(coordinator, 1)
    assert entity.available
    assert entity.unique_id == ADDRESS + "_zone_1"
    assert entity.device_info["identifiers"] == {(DOMAIN, ADDRESS)}
    await coordinator.async_shutdown()
