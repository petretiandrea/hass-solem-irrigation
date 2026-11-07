"""One atomic read snapshot per controller, shared by all entities."""
from asyncio import CancelledError, Lock
from dataclasses import replace
from datetime import timedelta
import logging

from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connection import async_validate_device, connection_scope
from .const import DOMAIN
from .data import WooBeeConfigEntry, WooBeeData
from .woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError
from .woobee_api.protocol import WooBeeV2

_LOGGER = logging.getLogger(__name__)
POLL_INTERVAL = timedelta(minutes=5)


class WooBeeCoordinator(DataUpdateCoordinator[WooBeeData]):
    """Reconnect and authenticate on every poll; never reuse expired sessions."""

    def __init__(self, hass: HomeAssistant, entry: WooBeeConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=POLL_INTERVAL)
        self.address = entry.data[CONF_ADDRESS]
        self._io_lock = Lock()

    async def _async_update_data(self) -> WooBeeData:
        try:
            async with self._io_lock:
                return await async_validate_device(self.hass, self.address)
        except AuthenticationError:
            # Fixed protocol key: no credentials a user can replace via reauth.
            # A fresh challenge on the next poll permits recovery without reload.
            # Transport exceptions may contain addresses or other sensitive text.
            raise UpdateFailed(
                "Controller authentication failed; next poll opens a fresh session"
            ) from None
        except (ConnectivityError, InvalidResponseError, TimeoutError):
            raise UpdateFailed(
                "Unable to read controller snapshot; check Bluetooth reachability and response data"
            ) from None

    async def async_irrigate(
        self, zone: int | None, minutes: int = 1, *, close_zone: bool = False,
    ) -> None:
        """Send once and publish observed state, serializing against reads.

        None means controller-wide stop. Starts never implicitly replace an
        active zone, including itself. With close_zone, stop only if the fresh
        active zone matches; an idle/different zone is a read-only no-op.
        """
        if zone is not None:
            try:
                WooBeeV2.start_valve_frame(zone, minutes)
            except ValueError as exc:
                raise ServiceValidationError(str(exc)) from exc
        async with self._io_lock:
            try:
                async with connection_scope(self.hass, self.address) as client:
                    if zone is not None:
                        before = await client.read_state()
                        self.async_set_updated_data(replace(self.data, state=before))
                        if close_zone:
                            if before.status.active_zone != zone:
                                return
                        elif before.status.active_zone is not None:
                            raise ServiceValidationError(
                                "Irrigation is already active. Stop all irrigation before starting a zone."
                            )
                    if zone is None or close_zone:
                        await client.stop()
                    else:
                        await client.start_valve(zone, minutes)
                    # A write or command reply alone is not success. Never resend.
                    after = await client.read_state()
                    self.async_set_updated_data(replace(self.data, state=after))
                    expected_zone = None if close_zone else zone
                    if after.status.active_zone != expected_zone:
                        raise HomeAssistantError(
                            "The controller did not confirm the requested irrigation state. "
                            "The command may have been rejected or may still be taking effect; "
                            "check the device before sending another command."
                        )
            except (AuthenticationError, ConnectivityError, InvalidResponseError, TimeoutError):
                self.async_set_update_error(UpdateFailed("Irrigation command outcome is unknown"))
                raise HomeAssistantError(
                    "Unable to confirm irrigation command. Check Bluetooth and controller state "
                    "before retrying; the command has not been repeated."
                ) from None
            except CancelledError:
                # Cancellation can happen after the controller received a start.
                self.async_set_update_error(UpdateFailed("Irrigation command cancelled; outcome unknown"))
                raise
