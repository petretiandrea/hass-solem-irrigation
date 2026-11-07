"""Verify real HA states, metadata, stable registry identity and shared updates."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.woobee_api import ConnectivityError
from test_coordinator import ADDRESS, snapshot


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS.upper()})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity(hass, domain, suffix):
    registry = er.async_get(hass)
    return registry.async_get(registry.async_get_entity_id(domain, DOMAIN, f"{ADDRESS}_{suffix}"))


def state(hass, domain, suffix):
    return hass.states.get(entity(hass, domain, suffix).entity_id)


@pytest.mark.parametrize("language, expected_name", [
    ("en", "Garden Zone 2 remaining time"),
    ("it", "Garden Tempo residuo zona 2"),
])
async def test_mapping_and_metadata(hass, language, expected_name):
    await hass.config.async_update(language=language)
    data = snapshot()
    data = replace(data, state=replace(data.state,
        status=replace(data.state.status, enabled=False, manual=True, sensor_open=True,
            clock_alarm=True, active_zone=3, zone_remaining_seconds=(0, 123, None, 456)),
        valve_faults=replace(data.state.valve_faults, faulty_zones=(2, 4))))
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=data) as read:
        entry = await setup(hass)
        assert read.await_count == 1
        for key, expected in {"connectivity":"on", "enabled":"off", "manual":"on",
                              "sensor_open":"on", "clock_alarm":"on"}.items():
            assert state(hass, "binary_sensor", key).state == expected
        for zone, value in enumerate(("0", "123", STATE_UNKNOWN, "456"), 1):
            duration = state(hass, "sensor", f"zone_{zone}_remaining_time")
            assert duration.state == value
            assert duration.attributes["unit_of_measurement"] == "s"
            assert duration.attributes["device_class"] == "duration"
            # A countdown is not accumulated usage or a periodic physical measurement.
            assert "state_class" not in duration.attributes
            assert state(hass, "binary_sensor", f"zone_{zone}_irrigating").state == ("on" if zone == 3 else "off")
            assert state(hass, "binary_sensor", f"zone_{zone}_valve_fault").state == ("on" if zone in (2, 4) else "off")
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 18
        device, = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        assert device.identifiers == {(DOMAIN, ADDRESS)}
        assert {item.device_id for item in entities} == {device.id}
        assert len({item.unique_id for item in entities}) == 18
        for item in entities:
            assert item.has_entity_name
            assert item.translation_key
        assert entity(hass, "binary_sensor", "clock_alarm").original_device_class == "problem"
        assert entity(hass, "binary_sensor", "connectivity").original_device_class == "connectivity"
        assert entity(hass, "binary_sensor", "zone_1_irrigating").original_device_class == "running"
        assert entity(hass, "binary_sensor", "zone_1_valve_fault").entity_category.value == "diagnostic"
        raw = entity(hass, "sensor", "battery_raw")
        assert raw.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert raw.entity_category.value == "diagnostic"
        assert raw.original_device_class is None
        assert hass.states.get(raw.entity_id) is None
        assert state(hass, "sensor", "zone_2_remaining_time").attributes["friendly_name"] == expected_name
        # Enabling the diagnostic sensor exposes the byte without inventing a scale.
        registry.async_update_entity(raw.entity_id, disabled_by=None)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        raw_state = hass.states.get(raw.entity_id)
        assert raw_state.state == "90"
        assert "unit_of_measurement" not in raw_state.attributes
        assert "state_class" not in raw_state.attributes
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failure_recovery_and_identity(hass):
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        entry = await setup(hass)
        before = {item.unique_id: (item.id, item.entity_id, item.device_id)
                  for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
        read.side_effect = ConnectivityError()
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert state(hass, "binary_sensor", "connectivity").state == "off"
        for domain, suffix in (("sensor", "zone_1_remaining_time"),
                               ("binary_sensor", "zone_1_irrigating"), ("binary_sensor", "enabled")):
            assert state(hass, domain, suffix).state == STATE_UNAVAILABLE
        data = snapshot()
        read.side_effect = None
        read.return_value = replace(data, device_info=replace(data.device_info,
            name="Renamed", serial="new serial", uuid="new uuid"),
            state=replace(data.state, status=replace(data.state.status,
                active_zone=4, zone_remaining_seconds=(0, 0, 0, 30))))
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert state(hass, "binary_sensor", "connectivity").state == "on"
        assert state(hass, "binary_sensor", "zone_4_irrigating").state == "on"
        assert state(hass, "sensor", "zone_4_remaining_time").state == "30"
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        after = {item.unique_id: (item.id, item.entity_id, item.device_id)
                 for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
        assert before == after
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert all((value := hass.states.get(entity_id)) is None or value.state == STATE_UNAVAILABLE
                   for _, entity_id, _ in before.values())


async def test_real_subscribers_own_polling(hass, freezer):
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        entry = await setup(hass)
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert read.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert read.await_count == 2


async def test_corebluetooth_identity_and_controller_namespaces(hass):
    uuid = "12345678-1234-5678-9ABC-123456789ABC"
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        first = await setup(hass)
        read.return_value = replace(snapshot(), address=uuid.lower())
        second = MockConfigEntry(domain=DOMAIN, unique_id=uuid.lower(), data={CONF_ADDRESS: uuid})
        second.add_to_hass(hass)
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        first_ids = {item.unique_id for item in er.async_entries_for_config_entry(registry, first.entry_id)}
        second_ids = {item.unique_id for item in er.async_entries_for_config_entry(registry, second.entry_id)}
        assert second_ids == {item.replace(ADDRESS, uuid.lower()) for item in first_ids}
        assert first_ids.isdisjoint(second_ids)
        device, = dr.async_entries_for_config_entry(dr.async_get(hass), second.entry_id)
        assert device.identifiers == {(DOMAIN, uuid.lower())}
        assert await hass.config_entries.async_unload(first.entry_id)
        assert await hass.config_entries.async_unload(second.entry_id)
