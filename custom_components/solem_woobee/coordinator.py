"""One atomic read snapshot per controller, shared by all entities."""
from asyncio import CancelledError, Lock
from dataclasses import replace
from datetime import timedelta
import logging

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .connection import async_validate_device, connection_scope
from .const import DOMAIN
from .data import WooBeeConfigEntry, WooBeeData
from .services import MAX_MINUTES
from .woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError
from .woobee_api.protocol import WooBeeV2

_LOGGER = logging.getLogger(__name__)
POLL_INTERVAL = timedelta(minutes=5)


class WooBeeCoordinator(DataUpdateCoordinator[WooBeeData]):
    """Reconnect and authenticate on every poll; never reuse expired sessions."""

    def __init__(self, hass: HomeAssistant, entry: WooBeeConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=POLL_INTERVAL)
        address: object = entry.data[CONF_ADDRESS]
        if not isinstance(address, str):
            raise ValueError("controller address must be a string")
        self.address = address
        # Freeze legacy address-derived registry IDs across transport changes.
        identity_address: object = entry.data.get("identity_address", address)
        if not isinstance(identity_address, str):
            raise ValueError("controller identity address must be a string")
        self.identity_address = identity_address
        self._io_lock = Lock()

    async def _async_update_data(self) -> WooBeeData:
        try:
            async with self._io_lock:
                data = await async_validate_device(self.hass, self.address)
                lookup_address = self.address.upper() if len(self.address) == 17 else self.address
                service_info = bluetooth.async_last_service_info(
                    self.hass, lookup_address, connectable=True,
                )
                return replace(
                    data, rssi=service_info.rssi if service_info is not None else None,
                    last_fetched=dt_util.utcnow(),
                )
        except AuthenticationError as exc:
            # Fixed protocol key: no credentials a user can replace via reauth.
            # A fresh challenge on the next poll permits recovery without reload.
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from exc
        except (ConnectivityError, InvalidResponseError, TimeoutError) as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="snapshot_failed"
            ) from exc

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
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_irrigation",
                    translation_placeholders={"max_minutes": str(MAX_MINUTES)},
                ) from exc
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
                                translation_domain=DOMAIN, translation_key="irrigation_active"
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
                            translation_domain=DOMAIN, translation_key="state_unconfirmed"
                        )
            except (AuthenticationError, ConnectivityError, InvalidResponseError, TimeoutError) as exc:
                self.async_set_update_error(UpdateFailed(translation_domain=DOMAIN, translation_key="command_failed"))
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="command_failed"
                ) from exc
            except CancelledError:
                # Cancellation can happen after the controller received a start.
                self.async_set_update_error(UpdateFailed(translation_domain=DOMAIN, translation_key="command_cancelled"))
                raise
