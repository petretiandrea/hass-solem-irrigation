"""Client failure causes, availability logs and recovery using synthetic data."""
import logging
import traceback
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.coordinator import WooBeeCoordinator
from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError, SessionTimeoutError,
)
from test_coordinator import ADDRESS, snapshot

ERROR_DETAIL = "Synthetic client failure"


@pytest.mark.parametrize("error_type", [AuthenticationError, ConnectivityError, InvalidResponseError, SessionTimeoutError, TimeoutError])
async def test_failure_and_recovery_logs(hass, caplog, error_type):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device",
               side_effect=[snapshot(), error_type(ERROR_DETAIL), error_type(ERROR_DETAIL), snapshot(), snapshot()]):
        with caplog.at_level(logging.DEBUG, logger="custom_components.solem_woobee.coordinator"):
            for _ in range(5):
                await coordinator.async_refresh()
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert ERROR_DETAIL not in messages
    assert ERROR_DETAIL in caplog.text  # HA DEBUG includes the original traceback.
    assert ADDRESS not in messages
    assert caplog.text.count("Error fetching") == 1
    assert caplog.text.count("data recovered") == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("error_type", [AuthenticationError, ConnectivityError, InvalidResponseError, SessionTimeoutError, TimeoutError])
async def test_command_error_retains_original_cause(hass, error_type):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    coordinator.async_set_updated_data(snapshot())
    connection = AsyncMock()
    original = error_type(ERROR_DETAIL)
    original.add_note(ERROR_DETAIL)
    connection.__aenter__.side_effect = original
    with patch("custom_components.solem_woobee.coordinator.connection_scope", return_value=connection):
        with pytest.raises(HomeAssistantError) as raised:
            await coordinator.async_irrigate(None)
    assert raised.value.__cause__ is original
    assert ERROR_DETAIL in "".join(traceback.format_exception(raised.value))
    assert original.__notes__ == [ERROR_DETAIL]
    assert not coordinator.last_update_success
    await coordinator.async_shutdown()


async def test_expired_session_reconnects_on_next_poll(hass):
    """A rejected challenge is retried only by the next new connection scope."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    expired, fresh = AsyncMock(), AsyncMock()
    expired.__aenter__.side_effect = AuthenticationError(ERROR_DETAIL)
    fresh.__aenter__.return_value.read_device_info.return_value = snapshot().device_info
    fresh.__aenter__.return_value.read_state.return_value = snapshot().state
    with patch("custom_components.solem_woobee.connection.connection_scope", side_effect=[expired, fresh]) as connect:
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert connect.call_count == 1
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator.data == snapshot()
        assert connect.call_count == 2
        fresh.__aexit__.assert_awaited_once()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("error_type", [AuthenticationError, ConnectivityError, InvalidResponseError, SessionTimeoutError, TimeoutError])
async def test_poll_error_retains_cause(hass, error_type):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    original = error_type(ERROR_DETAIL)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", side_effect=original):
        await coordinator.async_refresh()
    cause = coordinator.last_exception.__cause__
    assert cause is original
    assert ERROR_DETAIL in "".join(traceback.format_exception(coordinator.last_exception))
    await coordinator.async_shutdown()


@pytest.mark.parametrize("explicit_cause", [True, False])
async def test_nested_transport_traceback_is_preserved(hass, explicit_cause):
    """Both explicit causes and implicit contexts retain their stack locations."""
    original = None
    try:
        try:
            raise OSError(5, ERROR_DETAIL, ERROR_DETAIL)
        except OSError as transport:
            transport.add_note(ERROR_DETAIL)
            if explicit_cause:
                raise ConnectivityError(ERROR_DETAIL) from transport
            raise ConnectivityError(ERROR_DETAIL)
    except ConnectivityError as error:
        original = error

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    connection = AsyncMock()
    connection.__aenter__.side_effect = original
    with patch("custom_components.solem_woobee.coordinator.connection_scope", return_value=connection):
        with pytest.raises(HomeAssistantError) as raised:
            await coordinator.async_irrigate(None)
    assert raised.value.__cause__ is original
    assert ERROR_DETAIL in "".join(traceback.format_exception(raised.value))
    await coordinator.async_shutdown()
