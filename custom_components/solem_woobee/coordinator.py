"""One atomic read snapshot per controller, shared by all entities."""
from datetime import timedelta
import logging

from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connection import async_validate_device
from .const import DOMAIN
from .data import WooBeeConfigEntry, WooBeeData
from .woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError

_LOGGER = logging.getLogger(__name__)
POLL_INTERVAL = timedelta(minutes=5)


class WooBeeCoordinator(DataUpdateCoordinator[WooBeeData]):
    """Reconnect and authenticate on every poll; never reuse expired sessions."""

    def __init__(self, hass: HomeAssistant, entry: WooBeeConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=POLL_INTERVAL)
        self.address = entry.data[CONF_ADDRESS]

    async def _async_update_data(self) -> WooBeeData:
        try:
            return await async_validate_device(self.hass, self.address)
        except AuthenticationError as exc:
            # Fixed protocol key: no credentials a user can replace via reauth.
            # A fresh challenge on the next poll permits recovery without reload.
            raise UpdateFailed("Controller authentication failed") from exc
        except (ConnectivityError, InvalidResponseError, TimeoutError) as exc:
            raise UpdateFailed("Unable to read controller snapshot") from exc
