"""Manual irrigation action registration and strict duration schema."""
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN

MAX_MINUTES = 0xFFFFFF // 60


def valid_minutes(value: object) -> int:
    """Require whole minutes, rejecting bools, fractions and implicit coercion."""
    if type(value) is not int or not 1 <= value <= MAX_MINUTES:
        raise vol.Invalid(f"minutes must be an integer from 1 to {MAX_MINUTES}")
    return value


def async_setup_services(hass: HomeAssistant) -> None:
    """Register once during integration setup, even with no loaded entries."""
    async_register_platform_entity_service(
        hass, DOMAIN, "start_irrigation", entity_domain="button",
        schema={vol.Required("minutes"): valid_minutes},
        func="async_start_irrigation", required_features=[1],
    )
