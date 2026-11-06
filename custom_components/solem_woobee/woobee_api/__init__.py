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
from .responses import WooBeeDeviceInfo, WooBeeInputAlerts, WooBeeState, WooBeeStatus, WooBeeValveFaults
from .programs import (
    Days,
    ControllerBackup,
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
    "WooBeeDeviceInfo",
    "WooBeeState",
    "WooBeeStatus",
    "WooBeeValveFaults",
    "IrrigationProgram",
    "Days",
    "ControllerBackup",
    "ProgramCycle",
    "Schedule",
    "TimeOfDay",
    "Weekday",
    "ZoneDurations",
    "build_program_frames",
    "parse_program_replies",
]


from .client import WooBeeConnection
from .errors import WooBeeError, ConnectivityError, SessionTimeoutError, InvalidResponseError
from .models import ControllerIdentity, ZoneIdentity, normalize_address

__all__ += ["WooBeeConnection", "WooBeeError", "ConnectivityError", "SessionTimeoutError",
            "InvalidResponseError", "ControllerIdentity", "ZoneIdentity", "normalize_address"]
