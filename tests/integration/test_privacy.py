"""Client failures with synthetic secrets must stay anonymous, even at DEBUG."""
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
    AuthenticationError, ConnectivityError, InvalidResponseError,
)
from test_coordinator import ADDRESS, snapshot

SECRET = "anonymous@example.invalid password=synthetic-secret token=synthetic-token"


@pytest.mark.parametrize("error_type", [AuthenticationError, ConnectivityError, InvalidResponseError, TimeoutError])
async def test_private_failure_and_recovery_logs(hass, caplog, error_type):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device",
               side_effect=[snapshot(), error_type(SECRET), error_type(SECRET), snapshot(), snapshot()]):
        with caplog.at_level(logging.DEBUG, logger="custom_components.solem_woobee.coordinator"):
            for _ in range(5):
                await coordinator.async_refresh()
    assert SECRET not in caplog.text
    assert ADDRESS not in caplog.text
    assert caplog.text.count("Error fetching") == 1
    assert caplog.text.count("data recovered") == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("error_type", [AuthenticationError, ConnectivityError, InvalidResponseError, TimeoutError])
async def test_command_error_traceback_is_private(hass, error_type):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    coordinator.async_set_updated_data(snapshot())
    connection = AsyncMock()
    connection.__aenter__.side_effect = error_type(SECRET)
    with patch("custom_components.solem_woobee.coordinator.connection_scope", return_value=connection):
        with pytest.raises(HomeAssistantError) as raised:
            await coordinator.async_irrigate(None)
    assert SECRET not in "".join(traceback.format_exception(raised.value))
    assert not coordinator.last_update_success
    await coordinator.async_shutdown()


async def test_expired_session_reconnects_on_next_poll(hass):
    """A rejected challenge is retried only by the next new connection scope."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    expired, fresh = AsyncMock(), AsyncMock()
    expired.__aenter__.side_effect = AuthenticationError(SECRET)
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
