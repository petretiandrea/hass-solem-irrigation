"""SOLEM WooBee BLE client."""

from .client import GattCharacteristic, GattService, WooBeeClient, WooBeeProfile
from .protocol import (
    AuthenticationError,
    SOLEM_STANDARD_KEY,
    WOOBEE_V2_GATT,
    SolemGatt,
    SolemSession,
    WooBeeV2,
)
from .responses import WooBeeInputAlerts, WooBeeState, WooBeeStatus, WooBeeValveFaults
from .programs import (
    Days,
    IrrigationProgram,
    ProgramCycle,
    Schedule,
    TimeOfDay,
    Weekday,
    ZoneDurations,
    build_program_frames,
    parse_program_replies,
)

__all__ = [
    "AuthenticationError",
    "GattCharacteristic",
    "GattService",
    "SolemGatt",
    "SolemSession",
    "SOLEM_STANDARD_KEY",
    "WOOBEE_V2_GATT",
    "WooBeeClient",
    "WooBeeProfile",
    "WooBeeV2",
    "WooBeeInputAlerts",
    "WooBeeState",
    "WooBeeStatus",
    "WooBeeValveFaults",
    "IrrigationProgram",
    "Days",
    "ProgramCycle",
    "Schedule",
    "TimeOfDay",
    "Weekday",
    "ZoneDurations",
    "build_program_frames",
    "parse_program_replies",
]

