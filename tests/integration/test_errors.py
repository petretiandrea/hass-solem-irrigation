"""Client failure causes, availability logs and recovery using synthetic data."""
import json
import logging
from pathlib import Path
from string import Formatter
import traceback
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.coordinator import WooBeeCoordinator
from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError, SessionTimeoutError,
)
from custom_components.solem_woobee.services import MAX_MINUTES, valid_minutes
from test_commands import running, scope
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
        assert coordinator.data.state == snapshot().state
        assert coordinator.data.device_info == snapshot().device_info
        assert coordinator.data.last_fetched is not None
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


@pytest.mark.parametrize("language", ["en", "it"])
async def test_translated_validation_and_action_errors(hass, language):
    """HA resolves every exception key and its safe placeholders in both locales."""
    messages = await async_get_translations(hass, language, "exceptions", {DOMAIN})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    coordinator = WooBeeCoordinator(hass, entry)
    coordinator.async_set_updated_data(snapshot())
    client = AsyncMock()
    client.read_state.return_value = running(2)
    errors = []
    with pytest.raises(ServiceValidationError) as invalid:
        valid_minutes(True)
    errors.append(invalid.value)
    with patch("custom_components.solem_woobee.coordinator.connection_scope", return_value=scope(client)) as connect:
        with pytest.raises(ServiceValidationError) as invalid:
            await coordinator.async_irrigate(5)
        errors.append(invalid.value)
        assert isinstance(invalid.value.__cause__, ValueError)
        connect.assert_not_called()
        with pytest.raises(ServiceValidationError) as busy:
            await coordinator.async_irrigate(1)
        errors.append(busy.value)
        client.start_valve.assert_not_awaited()
        with pytest.raises(HomeAssistantError) as mismatch:
            await coordinator.async_irrigate(None)
        errors.append(mismatch.value)
        original = ConnectivityError(ERROR_DETAIL)
        client.stop.side_effect = original
        with pytest.raises(HomeAssistantError) as failed:
            await coordinator.async_irrigate(None)
        errors.append(failed.value)
        assert failed.value.__cause__ is original
    assert [error.translation_key for error in errors] == [
        "invalid_minutes", "invalid_irrigation", "irrigation_active", "state_unconfirmed", "command_failed",
    ]
    for error in errors:
        assert error.translation_domain == DOMAIN
        template = messages[f"component.{DOMAIN}.exceptions.{error.translation_key}.message"]
        rendered = template.format(**(error.translation_placeholders or {}))
        assert "{" not in rendered
        assert ERROR_DETAIL not in rendered
        if error.translation_key.startswith("invalid"):
            assert str(MAX_MINUTES) in rendered
    assert ("Impossibile" if language == "it" else "Unable to confirm") in rendered
    await coordinator.async_shutdown()


def test_exception_catalogs_match():
    """Every locale has the same keys and placeholder names as source strings."""
    catalogs = [json.loads((Path(__file__).parents[2] /
        "custom_components/solem_woobee" / name).read_text())["exceptions"]
        for name in ("strings.json", "translations/en.json", "translations/it.json")]
    source, english, italian = catalogs
    assert source == english
    assert source.keys() == italian.keys()
    for key in source:
        assert {field for _, field, _, _ in Formatter().parse(source[key]["message"]) if field} == {
            field for _, field, _, _ in Formatter().parse(italian[key]["message"]) if field
        }
