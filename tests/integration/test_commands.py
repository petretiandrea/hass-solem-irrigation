"""Manual commands through HA services and a simulated WooBee client."""
import asyncio
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.helpers.selector import TargetSelector, validate_selector
from homeassistant.util.yaml import load_yaml_dict

from custom_components.solem_woobee.services import MAX_MINUTES, valid_minutes
from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError,
)
from test_coordinator import snapshot
from test_entities import setup, state, entity


def running(zone):
    data = snapshot()
    return replace(data.state, status=replace(data.state.status, active_zone=zone,
                   zone_remaining_seconds=(60, 0, 0, 0)))


def scope(client):
    result = AsyncMock()
    result.__aenter__.return_value = client
    return result


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "2", None, MAX_MINUTES + 1])
def test_invalid_duration(value):
    with pytest.raises(vol.Invalid):
        valid_minutes(value)


@pytest.mark.parametrize("value", [1, MAX_MINUTES])
def test_duration_bounds(value):
    assert valid_minutes(value) == value


@pytest.mark.parametrize("language, name", [
    ("en", "Garden Zone 1"),
    ("it", "Garden Zona 1"),
])
async def test_commands_and_lifecycle(hass, language, name):
    await hass.config.async_update(language=language)
    client = AsyncMock()
    client.read_state.side_effect = [running(None), running(1), running(None), running(1), running(None)]
    connection = scope(client)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=connection,
    ):
        entry = await setup(hass)
        start = entity(hass, "valve", "zone_1")
        stop = entity(hass, "button", "stop_all")
        assert start.device_id == stop.device_id
        assert start.entity_category is None
        assert start.translation_key == "zone"
        assert state(hass, "valve", "zone_1").attributes["friendly_name"] == name
        await hass.services.async_call("valve", "open_valve", {"entity_id": start.entity_id}, blocking=True)
        client.start_valve.assert_awaited_once_with(1, 1)
        assert state(hass, "binary_sensor", "zone_1_irrigating").state == "on"
        # Explicit controller stop before starting another timed run.
        await hass.services.async_call("button", "press", {"entity_id": stop.entity_id}, blocking=True)
        client.stop.assert_awaited_once()
        client.read_state.side_effect = [running(None), running(1)]
        await hass.services.async_call("solem_woobee", "start_irrigation",
            {"entity_id": start.entity_id, "minutes": 3}, blocking=True)
        assert client.start_valve.await_args.args == (1, 3)
        before = start.unique_id
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entity(hass, "valve", "zone_1").unique_id == before
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert hass.states.get(start.entity_id).state == "unavailable"
    assert connection.__aexit__.await_count == 3


@pytest.mark.parametrize("operation", ["start_valve", "stop", "read_state"])
@pytest.mark.parametrize("error", [ConnectivityError(), AuthenticationError(), InvalidResponseError(), TimeoutError()])
async def test_failure_no_retry_or_success(hass, operation, error):
    client = AsyncMock()
    client.read_state.return_value = running(None)
    getattr(client, operation).side_effect = error
    connection = scope(client)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=connection,
    ):
        entry = await setup(hass)
        domain, action, suffix = ("button", "press", "stop_all") if operation == "stop" else ("valve", "open_valve", "zone_1")
        target = entity(hass, domain, suffix).entity_id
        previous = hass.states.get(target).state
        with pytest.raises(HomeAssistantError, match="Unable to confirm"):
            await hass.services.async_call(domain, action, {"entity_id": target}, blocking=True)
        assert getattr(client, operation).await_count == 1
        assert not entry.runtime_data.last_update_success
        # A failed opening never publishes an optimistic open state.
        assert entry.runtime_data.data.state.status.active_zone is None
        assert hass.states.get(target).state in (previous, "unavailable")
        connection.__aexit__.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("zone, observed", [(1, None), (None, 2)])
async def test_unconfirmed_result_is_published_but_raises(hass, zone, observed):
    client = AsyncMock()
    client.read_state.side_effect = [running(None), running(observed)] if zone else [running(observed)]
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ):
        entry = await setup(hass)
        with pytest.raises(HomeAssistantError, match="did not confirm"):
            await entry.runtime_data.async_irrigate(zone)
        assert entry.runtime_data.data.state.status.active_zone == observed
        assert client.start_valve.await_count + client.stop.await_count == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_busy_invalid_and_serialized(hass):
    client = AsyncMock()
    client.read_state.return_value = running(2)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read, patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ) as connect:
        entry = await setup(hass)
        coordinator = entry.runtime_data
        with pytest.raises(ServiceValidationError):
            await coordinator.async_irrigate(5)
        connect.assert_not_called()
        with pytest.raises(ServiceValidationError, match="already active"):
            await coordinator.async_irrigate(1)
        client.start_valve.assert_not_awaited()
        assert coordinator.data.state.status.active_zone == 2
        entered, release = asyncio.Event(), asyncio.Event()
        async def stop():
            entered.set()
            await release.wait()
        client.stop.side_effect = stop
        client.read_state.return_value = running(None)
        command = asyncio.create_task(coordinator.async_irrigate(None))
        await entered.wait()
        poll = asyncio.create_task(coordinator.async_refresh())
        await asyncio.sleep(0)
        assert read.await_count == 1
        release.set()
        await asyncio.gather(command, poll)
        assert read.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_post_write_timeout_and_recovery(hass):
    client = AsyncMock()
    client.read_state.side_effect = [running(None), TimeoutError()]
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ):
        entry = await setup(hass)
        with pytest.raises(HomeAssistantError):
            await entry.runtime_data.async_irrigate(1)
        client.start_valve.assert_awaited_once_with(1, 1)
        assert not entry.runtime_data.last_update_success
        await entry.runtime_data.async_refresh()
        assert entry.runtime_data.last_update_success
        client.start_valve.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_action_registered_without_entries(hass):
    from_config = {}
    assert await async_setup_component(hass, "solem_woobee", from_config)
    assert hass.services.has_service("solem_woobee", "start_irrigation")
    with pytest.raises(vol.Invalid):
        await hass.services.async_call("solem_woobee", "start_irrigation",
            {"entity_id": "button.missing", "minutes": 1.5}, blocking=True)


async def test_cancel_does_not_replay_and_releases_lock(hass):
    client = AsyncMock()
    client.read_state.return_value = running(None)
    entered = asyncio.Event()
    async def start(*args):
        entered.set()
        await asyncio.Event().wait()
    client.start_valve.side_effect = start
    connection = scope(client)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=connection,
    ):
        entry = await setup(hass)
        command = asyncio.create_task(entry.runtime_data.async_irrigate(1))
        await entered.wait()
        command.cancel()
        with pytest.raises(asyncio.CancelledError):
            await command
        assert not entry.runtime_data.last_update_success
        connection.__aexit__.assert_awaited_once()
        await entry.runtime_data.async_refresh()
        assert entry.runtime_data.last_update_success
        client.start_valve.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("zone", [1, 2, 3, 4])
async def test_duration_action_routes_each_zone(hass, zone):
    client = AsyncMock()
    client.read_state.side_effect = [running(None), running(zone)]
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ):
        entry = await setup(hass)
        await hass.services.async_call("solem_woobee", "start_irrigation",
            {"entity_id": entity(hass, "valve", f"zone_{zone}").entity_id,
             "minutes": MAX_MINUTES}, blocking=True)
        client.start_valve.assert_awaited_once_with(zone, MAX_MINUTES)
        assert state(hass, "binary_sensor", f"zone_{zone}_irrigating").state == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_action_description_schema_and_stop_target(hass):
    """Validate UI metadata too: service calls alone don't validate services.yaml."""
    description = load_yaml_dict(str(Path(__file__).parents[2] /
        "custom_components/solem_woobee/services.yaml"))["start_irrigation"]
    target = TargetSelector.CONFIG_SCHEMA(description["target"])
    assert target["entity"] == [{"domain": ["valve"], "integration": "solem_woobee"}]
    assert validate_selector(description["fields"]["minutes"]["selector"])
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope",
    ) as connect:
        entry = await setup(hass)
        # HA ignores targets outside the valve platform; a stop button must
        # never reach the start handler or open a BLE session.
        await hass.services.async_call("solem_woobee", "start_irrigation",
            {"entity_id": entity(hass, "button", "stop_all").entity_id,
             "minutes": 1}, blocking=True)
        connect.assert_not_called()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("active", [None, 1, 2])
async def test_conditional_close_reads_fresh_state(hass, active):
    """An HA close cannot intentionally stop another active zone."""
    client = AsyncMock()
    client.read_state.side_effect = [running(active), running(None)]
    connection = scope(client)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=connection,
    ):
        entry = await setup(hass)
        await hass.services.async_call("valve", "close_valve",
            {"entity_id": entity(hass, "valve", "zone_1").entity_id}, blocking=True)
        assert client.stop.await_count == (1 if active == 1 else 0)
        assert client.read_state.await_count == (2 if active == 1 else 1)
        client.start_valve.assert_not_awaited()
        assert state(hass, "valve", "zone_1").state == "closed"
        assert state(hass, "valve", "zone_2").state == ("open" if active == 2 else "closed")
        connection.__aexit__.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_default_duration_persisted_and_override_is_temporary(hass):
    client = AsyncMock()
    client.read_state.side_effect = [running(None), running(1), running(None), running(1)]
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ) as connect:
        entry = await setup(hass)
        target = entity(hass, "valve", "zone_1").entity_id
        await hass.services.async_call("solem_woobee", "set_default_duration",
            {"entity_id": target, "minutes": 5}, blocking=True)
        connect.assert_not_called()
        assert state(hass, "valve", "zone_1").attributes["default_duration_minutes"] == 5
        assert state(hass, "valve", "zone_2").attributes["default_duration_minutes"] == 1
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert state(hass, "valve", "zone_1").attributes["default_duration_minutes"] == 5
        await hass.services.async_call("valve", "open_valve", {"entity_id": target}, blocking=True)
        client.start_valve.assert_awaited_once_with(1, 5)
        # Simulate a completed timed run before a second request.
        await hass.services.async_call("solem_woobee", "start_irrigation",
            {"entity_id": target, "minutes": 2}, blocking=True)
        assert client.start_valve.await_args.args == (1, 2)
        assert state(hass, "valve", "zone_1").attributes["default_duration_minutes"] == 5
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_valve_metadata_and_failure_recovery(hass):
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        entry = await setup(hass)
        for zone in range(1, 5):
            valve = state(hass, "valve", f"zone_{zone}")
            assert valve.state == "closed"
            assert valve.attributes["device_class"] == "water"
            assert valve.attributes["supported_features"] == 3
            assert "current_position" not in valve.attributes
        # Missing countdown pages must not turn a known idle valve into unknown.
        assert state(hass, "valve", "zone_3").state == "closed"
        read.side_effect = ConnectivityError()
        await entry.runtime_data.async_refresh()
        assert state(hass, "valve", "zone_1").state == "unavailable"
        read.side_effect = None
        read.return_value = replace(snapshot(), state=running(3))
        await entry.runtime_data.async_refresh()
        assert state(hass, "valve", "zone_3").state == "open"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("failure", [TimeoutError(), ConnectivityError(), InvalidResponseError()])
async def test_close_failure_does_not_report_closed_or_retry(hass, failure):
    client = AsyncMock()
    client.read_state.return_value = running(1)
    client.stop.side_effect = failure
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ):
        entry = await setup(hass)
        with pytest.raises(HomeAssistantError, match="Unable to confirm"):
            await hass.services.async_call("valve", "close_valve",
                {"entity_id": entity(hass, "valve", "zone_1").entity_id}, blocking=True)
        client.stop.assert_awaited_once()
        assert state(hass, "valve", "zone_1").state == "unavailable"
        assert entry.runtime_data.data.state.status.active_zone == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_close_unconfirmed_and_invalid_default(hass):
    client = AsyncMock()
    client.read_state.return_value = running(1)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()), patch(
        "custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client),
    ) as connect:
        entry = await setup(hass)
        target = entity(hass, "valve", "zone_1").entity_id
        with pytest.raises(vol.Invalid):
            await hass.services.async_call("solem_woobee", "set_default_duration",
                {"entity_id": target, "minutes": True}, blocking=True)
        assert not entry.options
        connect.assert_not_called()
        with pytest.raises(HomeAssistantError, match="did not confirm"):
            await hass.services.async_call("valve", "close_valve", {"entity_id": target}, blocking=True)
        assert state(hass, "valve", "zone_1").state == "open"
        client.stop.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)
