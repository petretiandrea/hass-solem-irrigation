"""Readable WooBee V2 responses reconstructed from MySOLEM Java parsers."""

from __future__ import annotations

from dataclasses import dataclass


def _u24(high: int, middle: int, low: int) -> int:
    """APK `int3Value()`, with status high byte masked by `CMD_ID_V2` (0x0f)."""
    return ((high & 0x0F) << 16) | (middle << 8) | low


@dataclass(frozen=True)
class WooBeeStatus:
    """`BluetoothV6FrameManager.statusAnswerV5()` fields for WB-4."""

    enabled: bool
    manual: bool
    sensor_open: bool
    clock_alarm: bool
    rain_delay: int | None
    battery_raw: int
    active_program: int
    active_zone: int | None
    remaining_seconds: int | None
    zone_remaining_seconds: tuple[int, int, int, int]
    raw_pages: tuple[bytes, ...]


@dataclass(frozen=True)
class WooBeeValveFaults:
    """`cmdResetValveAnswer()` bitmaps. Zones are one-based."""

    faulty_zones: tuple[int, ...]
    raw: bytes


@dataclass(frozen=True)
class WooBeeInputAlerts:
    """Raw `readInputsAlertsAnswer()` frames.

    MySOLEM needs installed input configuration to label alert bitmaps. WB-4
    status replies without payload are retained verbatim instead of guessed.
    """

    raw_frames: tuple[bytes, ...]


@dataclass(frozen=True)
class WooBeeDeviceInfo:
    """MySOLEM `identificationAnswerV5()` and `readUUIDanswer()` fields."""

    name: str | None
    bluetooth_address: str | None
    hardware: str | None
    firmware: str | None
    serial: str | None
    uuid: str | None
    raw_identification: tuple[bytes, ...]
    raw_uuid: tuple[bytes, ...]


@dataclass(frozen=True)
class WooBeeState:
    status: WooBeeStatus
    valve_faults: WooBeeValveFaults
    input_alerts: WooBeeInputAlerts


def parse_device_info(identity_replies: list[bytes] | tuple[bytes, ...], uuid_replies: list[bytes] | tuple[bytes, ...]) -> WooBeeDeviceInfo:
    """Parse V5 identity pages exactly as MySOLEM does; missing pages stay None."""
    name = bluetooth_address = hardware = firmware = serial = None
    for reply in identity_replies:
        if len(reply) < 3 or reply[0] != 0x10:
            continue
        if reply[2] == 0:
            name = reply[3:18].split(b"\0", 1)[0].decode("utf-8")
        elif reply[2] == 1 and len(reply) >= 17:
            address = reply[3:9].hex().upper()
            bluetooth_address = address
            hardware = chr(reply[11])
            firmware = f"{reply[12]}.{reply[13]}.{reply[14]}"
            serial = f"{reply[9]:02X}{reply[10]:02X}{address[6:]}{reply[16]:02X}{reply[15]:02X}"
    uuid = None
    for reply in uuid_replies:
        if len(reply) >= 2 and reply[0] == 0xE4:
            uuid = reply[2:].hex().upper()
    return WooBeeDeviceInfo(
        name=name,
        bluetooth_address=bluetooth_address,
        hardware=hardware,
        firmware=firmware,
        serial=serial,
        uuid=uuid,
        raw_identification=tuple(identity_replies),
        raw_uuid=tuple(uuid_replies),
    )


def parse_status(replies: list[bytes] | tuple[bytes, ...]) -> WooBeeStatus:
    """Parse V6 status pages 2, 1, 0 exactly as MySOLEM's Java code does."""
    pages = {reply[2]: reply for reply in replies if len(reply) >= 3 and reply[0] == 0x3C}
    general = pages.get(2)
    if general is None or len(general) < 18:
        raise ValueError("missing or truncated WooBee V2 status page 2")

    zone_seconds: list[int | None] = [None] * 12
    for page, first_zone, offset, count in ((2, 1, 12, 2), (1, 3, 3, 5), (0, 8, 3, 5)):
        reply = pages.get(page)
        if reply is None:
            continue
        for index in range(count):
            start = offset + (index * 3)
            if start + 2 >= len(reply):
                break
            zone_seconds[first_zone + index - 1] = _u24(*reply[start : start + 3])

    active = general[9]
    active_zone = active if 1 <= active <= 4 else None
    return WooBeeStatus(
        enabled=bool(general[3] & 0x40),
        manual=0 < (general[3] & 0x0F) < 5,
        sensor_open=bool(general[3] & 0x80),
        clock_alarm=bool(general[3] & 0x20),
        rain_delay=(general[4] & 0x3F) or None,
        battery_raw=general[10],
        active_program=general[8],
        active_zone=active_zone,
        remaining_seconds=zone_seconds[active_zone - 1] if active_zone else None,
        zone_remaining_seconds=tuple((value or 0) for value in zone_seconds[:4]),
        raw_pages=tuple(replies),
    )


def parse_valve_faults(reply: bytes) -> WooBeeValveFaults:
    """Parse one V6 response to `readValveStatusV5()` / command 0x19."""
    if len(reply) < 5 or reply[0] != 0x1A:
        raise ValueError("invalid WooBee valve-status response")
    zones_1_to_8, zones_9_to_16 = reply[4], reply[3]
    faults = tuple(
        zone
        for zone in range(1, 17)
        if ((zones_1_to_8 if zone <= 8 else zones_9_to_16) >> ((zone - 1) % 8)) & 1
    )
    return WooBeeValveFaults(faulty_zones=faults, raw=reply)


def parse_state(raw: dict[str, list[bytes]]) -> WooBeeState:
    """Turn `WooBeeV2.read_state_raw()` data into MySOLEM-equivalent fields."""
    valve_replies = raw["valve_status"]
    if not valve_replies:
        raise ValueError("missing WooBee valve-status response")
    return WooBeeState(
        status=parse_status(raw["status"]),
        valve_faults=parse_valve_faults(valve_replies[-1]),
        input_alerts=WooBeeInputAlerts(raw_frames=tuple(raw["input_alerts"])),
    )
