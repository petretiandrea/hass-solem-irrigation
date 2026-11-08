"""WB-4 irrigation-program frames recovered from `configIrriV5()` in MySOLEM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum, IntFlag
import json


class Weekday(IntEnum):
    """MySOLEM `IrrigationProgram` bit positions: Monday bit 0 through Sunday bit 6."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class ProgramCycle(IntEnum):
    CUSTOM = 0
    EVEN_DAYS = 1
    ODD_DAYS = 2
    ODD_DAYS_EXCEPT_31 = 3
    PERIODIC = 4


class Days(IntFlag):
    """Schedule days. Values match MySOLEM weekday bits."""

    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 4
    THURSDAY = 8
    FRIDAY = 16
    SATURDAY = 32
    SUNDAY = 64
    EVERY_DAY = 127


@dataclass(frozen=True)
class TimeOfDay:
    hour: int
    minute: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.hour < 24 or not 0 <= self.minute < 60:
            raise ValueError("time must be within 00:00..23:59")

    @property
    def minutes_since_midnight(self) -> int:
        return (self.hour * 60) + self.minute


@dataclass(frozen=True)
class ZoneDurations:
    """Durations for four WB-4 zones, stored losslessly in seconds."""

    seconds: tuple[int, int, int, int]

    def __post_init__(self) -> None:
        if len(self.seconds) != 4 or any(not 0 <= value <= 0xFFFFFF for value in self.seconds):
            raise ValueError("four zone durations must fit 24-bit seconds")

    @classmethod
    def minutes(cls, *, one: int = 0, two: int = 0, three: int = 0, four: int = 0) -> "ZoneDurations":
        if any(not isinstance(value, int) or value < 0 for value in (one, two, three, four)):
            raise ValueError("zone durations must be non-negative whole minutes")
        return cls((one * 60, two * 60, three * 60, four * 60))

    @classmethod
    def from_seconds(cls, values: tuple[int, int, int, int]) -> "ZoneDurations":
        return cls(values)


@dataclass(frozen=True)
class IrrigationProgram:
    """Writable WB-4 irrigation program.

    Start times use minutes after midnight. ``None`` maps to MySOLEM's disabled
    sentinel 1440. Durations are seconds. WB-4 has four zones and eight starts.
    """

    index: int
    name: str = ""
    weekdays: frozenset[Weekday] = frozenset(Weekday)
    start_minutes: tuple[int | None, ...] = (None,) * 8
    zone_durations_seconds: tuple[int, ...] = (0,) * 4
    cycle: ProgramCycle = ProgramCycle.CUSTOM
    water_budget: int = 100
    time_between_zones: int = 0
    period_length: int = 2
    synchronization_day: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.index <= 11:
            raise ValueError("program index must be from 0 to 11")
        if len(self.name.encode()) > 31:
            raise ValueError("program name must contain at most 31 encoded bytes")
        if len(self.start_minutes) != 8:
            raise ValueError("exactly 8 start times are required")
        if len(self.zone_durations_seconds) != 4:
            raise ValueError("exactly 4 WB-4 zone durations are required")
        if any(value is not None and not 0 <= value < 1440 for value in self.start_minutes):
            raise ValueError("start times must be minutes from midnight or None")
        if any(not 0 <= value <= 0xFFFFFF for value in self.zone_durations_seconds):
            raise ValueError("zone durations must fit MySOLEM's 24-bit seconds")
        if not 0 <= self.water_budget <= 0xFFFF:
            raise ValueError("water budget must fit 16 bits")
        if not 0 <= self.time_between_zones <= 0xFFFF:
            raise ValueError("time between zones must fit 16 bits")
        if not 0 <= self.period_length <= 0xFF:
            raise ValueError("period length must fit 8 bits")
        if not 0 <= self.synchronization_day <= 0xFF:
            raise ValueError("synchronization day must fit 8 bits")

    @property
    def weekdays_mask(self) -> int:
        return sum(1 << day.value for day in self.weekdays)

    @property
    def number(self) -> int:
        """One-based program number for display and `Schedule`."""
        return self.index + 1

    @property
    def starts(self) -> tuple[str, ...]:
        """Configured start times as ``HH:MM``; disabled slots are omitted."""
        return tuple(f"{value // 60:02d}:{value % 60:02d}" for value in self.start_minutes if value is not None)

    @property
    def zone_minutes(self) -> dict[int, int]:
        """Whole-minute zone durations, keyed by one-based zone number."""
        return {zone: seconds // 60 for zone, seconds in enumerate(self.zone_durations_seconds, 1) if seconds}


@dataclass(frozen=True)
class Schedule:
    """Human-facing WB-4 program. Convert to wire model only at BLE seam."""

    number: int
    name: str = ""
    days: Days = Days.EVERY_DAY
    starts: tuple[TimeOfDay, ...] = ()
    zones: ZoneDurations = field(default_factory=lambda: ZoneDurations.minutes())
    cycle: ProgramCycle = ProgramCycle.CUSTOM
    water_budget: int = 100
    zone_pause_seconds: int = 0
    period_length: int = 2
    synchronization_day: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 12:
            raise ValueError("schedule number must be from 1 to 12")
        if len(self.starts) > 8:
            raise ValueError("WB-4 supports at most 8 start times")
        if not 0 <= self.water_budget <= 0xFFFF:
            raise ValueError("water budget must fit 16 bits")
        if not 0 <= self.zone_pause_seconds <= 0xFFFF:
            raise ValueError("zone pause must fit 16-bit seconds")
        if not 1 <= self.period_length <= 255:
            raise ValueError("period length must be from 1 to 255 days")
        if not 0 <= self.synchronization_day < self.period_length:
            raise ValueError("synchronization day must be within periodic cycle")

    def to_program(self) -> IrrigationProgram:
        weekdays = frozenset(day for day in Weekday if self.days & Days(1 << day.value))
        return IrrigationProgram(
            index=self.number - 1,
            name=self.name,
            weekdays=weekdays,
            start_minutes=tuple(time.minutes_since_midnight for time in self.starts) + (None,) * (8 - len(self.starts)),
            zone_durations_seconds=self.zones.seconds,
            cycle=self.cycle,
            water_budget=self.water_budget,
            time_between_zones=self.zone_pause_seconds,
            period_length=self.period_length,
            synchronization_day=self.synchronization_day,
        )

    @classmethod
    def from_program(cls, program: IrrigationProgram) -> "Schedule":
        return cls(
            number=program.number,
            name=program.name,
            days=Days(program.weekdays_mask),
            starts=tuple(TimeOfDay(value // 60, value % 60) for value in program.start_minutes if value is not None),
            zones=ZoneDurations.from_seconds((
                program.zone_durations_seconds[0], program.zone_durations_seconds[1],
                program.zone_durations_seconds[2], program.zone_durations_seconds[3],
            )),
            cycle=program.cycle,
            water_budget=program.water_budget,
            zone_pause_seconds=program.time_between_zones,
            period_length=program.period_length,
            synchronization_day=program.synchronization_day,
        )


@dataclass(frozen=True)
class ControllerBackup:
    """Portable backup of WB-4 schedules, independent of BLE frame layout."""

    schedules: tuple[Schedule, ...]

    def __post_init__(self) -> None:
        if len({schedule.number for schedule in self.schedules}) != len(self.schedules):
            raise ValueError("backup contains duplicate schedule numbers")

    def to_json(self) -> str:
        return json.dumps(
            {
                "format": "solem-woobee-backup/v1",
                "schedules": [
                    {
                        "number": schedule.number,
                        "name": schedule.name,
                        "days": int(schedule.days),
                        "starts": [{"hour": time.hour, "minute": time.minute} for time in schedule.starts],
                        "zone_seconds": list(schedule.zones.seconds),
                        "cycle": int(schedule.cycle),
                        "water_budget": schedule.water_budget,
                        "zone_pause_seconds": schedule.zone_pause_seconds,
                        "period_length": schedule.period_length,
                        "synchronization_day": schedule.synchronization_day,
                    }
                    for schedule in self.schedules
                ],
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> "ControllerBackup":
        payload = _mapping(json.loads(value))
        if payload.get("format") != "solem-woobee-backup/v1":
            raise ValueError("not a solem-woobee backup v1")
        schedules = _sequence(payload.get("schedules"))
        try:
            return cls(tuple(_schedule(item) for item in schedules))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid solem-woobee backup") from exc


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("expected an object with string keys")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("expected a sequence")
    return list(value)


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("expected an integer")
    return value


def _schedule(value: object) -> Schedule:
    item = _mapping(value)
    name = item.get("name", "")
    if not isinstance(name, str):
        raise ValueError("expected a schedule name")
    starts = [_mapping(time) for time in _sequence(item.get("starts", []))]
    seconds = [_integer(second) for second in _sequence(item.get("zone_seconds", (0, 0, 0, 0)))]
    if len(seconds) != 4:
        raise ValueError("expected four zone durations")
    return Schedule(
        number=_integer(item["number"]), name=name,
        days=Days(_integer(item.get("days", int(Days.EVERY_DAY)))),
        starts=tuple(TimeOfDay(_integer(time["hour"]), _integer(time.get("minute", 0))) for time in starts),
        zones=ZoneDurations.from_seconds((seconds[0], seconds[1], seconds[2], seconds[3])),
        cycle=ProgramCycle(_integer(item.get("cycle", int(ProgramCycle.CUSTOM)))),
        water_budget=_integer(item.get("water_budget", 100)),
        zone_pause_seconds=_integer(item.get("zone_pause_seconds", 0)),
        period_length=_integer(item.get("period_length", 2)),
        synchronization_day=_integer(item.get("synchronization_day", 0)),
    )


def build_program_frames(program: IrrigationProgram, today: date | None = None) -> list[bytes]:
    """Exact frame order emitted by MySOLEM `configIrriV5()` for irrigation."""
    today = today or date.today()
    identifier = program.index | 0x10
    name = program.name.encode()[:31].ljust(31, b"\0")
    frames = [
        bytes((0x2F, 0x12, 0, identifier)) + name[:16],
        bytes((0x2F, 0x12, 1, identifier)) + name[16:] + b"\0",
        bytes(
            (
                0x37,
                0x0E,
                0,
                identifier,
                *program.time_between_zones.to_bytes(2, "big"),
                *program.water_budget.to_bytes(2, "big"),
                int(program.cycle),
                program.weekdays_mask,
                program.period_length,
                program.synchronization_day,
                today.day,
                today.month,
                *(today.year.to_bytes(2, "big")),
            )
        ),
    ]
    starts = b"".join((1440 if value is None else value).to_bytes(2, "big") for value in program.start_minutes)
    frames.append(bytes((0x37, 0x12, 1, identifier)) + starts)
    durations = list(program.zone_durations_seconds) + [0] * 8
    for page, values in ((2, durations[:5]), (3, durations[5:10]), (4, durations[10:])):
        payload = b"".join(value.to_bytes(3, "big") for value in values)
        frames.append(bytes((0x37, len(payload) + 2, page, identifier)) + payload)
    return frames


def parse_program_replies(replies: list[bytes] | tuple[bytes, ...]) -> tuple[IrrigationProgram, ...]:
    """Parse `readConfigAnswerV5()` irrigation pages returned by command 0x39.

    Java computes page as ``first_IT - response[2]`` and reads descriptor from
    ``response[3]``. This function accepts one or more returned programs.
    """
    grouped: dict[int, list[bytes]] = {}
    for reply in replies:
        if len(reply) < 4 or reply[0] != 0x3A or (reply[3] >> 4) != 1:
            continue
        grouped.setdefault(reply[3] & 0x0F, []).append(reply)

    programs = []
    for index, frames in sorted(grouped.items()):
        first_it = max(frame[2] for frame in frames)
        pages = {first_it - frame[2]: frame for frame in frames}
        required = (0, 1, 2, 3, 4)
        if any(page not in pages for page in required):
            raise ValueError(f"truncated irrigation program {index} response")
        name = (pages[0][4:] + pages[1][4:]).split(b"\0", 1)[0].decode("utf-8")
        config = pages[2]
        starts = pages[3]
        durations = pages[4]
        if len(config) < 11 or len(starts) < 20 or len(durations) < 16:
            raise ValueError(f"truncated irrigation program {index} page")
        start_minutes = tuple(
            None if (value := int.from_bytes(starts[offset : offset + 2], "big")) >= 1440 else value
            for offset in range(4, 20, 2)
        )
        zone_durations = tuple(
            int.from_bytes(durations[offset : offset + 3], "big") for offset in range(4, 16, 3)
        )
        weekdays = frozenset(day for day in Weekday if config[9] & (1 << day.value))
        programs.append(
            IrrigationProgram(
                index=index,
                name=name,
                weekdays=weekdays,
                start_minutes=start_minutes,
                zone_durations_seconds=zone_durations,
                cycle=ProgramCycle(config[8]),
                water_budget=int.from_bytes(config[6:8], "big"),
                time_between_zones=int.from_bytes(config[4:6], "big"),
                period_length=config[10],
            )
        )
    if not programs:
        raise ValueError("no irrigation-program pages in response")
    return tuple(programs)
