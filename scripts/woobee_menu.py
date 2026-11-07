"""Interactive CLI for a SOLEM WooBee V2/WB-4."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from pathlib import Path
import sys

from bleak import BleakClient
from bleak.exc import BleakError

from woobee_api import (
    ControllerBackup,
    Days,
    ProgramCycle,
    Schedule,
    SolemSession,
    ConnectivityError,
    TimeOfDay,
    WOOBEE_V2_GATT,
    WooBeeV2,
    ZoneDurations,
)


DAY_OPTIONS = (
    (Days.MONDAY, "Lun"),
    (Days.TUESDAY, "Mar"),
    (Days.WEDNESDAY, "Mer"),
    (Days.THURSDAY, "Gio"),
    (Days.FRIDAY, "Ven"),
    (Days.SATURDAY, "Sab"),
    (Days.SUNDAY, "Dom"),
)


def ask_int(label: str, minimum: int, maximum: int) -> int:
    while True:
        try:
            value = int(input(f"{label}: "))
            if minimum <= value <= maximum:
                return value
        except ValueError:
            pass
        print(f"Inserisci valore {minimum}..{maximum}.")


def ask_time(label: str) -> TimeOfDay:
    while True:
        raw = input(f"{label} (HH:MM): ").strip()
        try:
            hour, minute = (int(part) for part in raw.split(":"))
            return TimeOfDay(hour, minute)
        except (ValueError, AttributeError):
            print("Formato richiesto: HH:MM.")


def format_days(days: Days) -> str:
    return ", ".join(label for flag, label in DAY_OPTIONS if days & flag) or "nessuno"


def format_schedule(schedule: Schedule) -> str:
    starts = ", ".join(f"{time.hour:02d}:{time.minute:02d}" for time in schedule.starts) or "nessuno"
    zones = ", ".join(
        f"Z{zone}={seconds // 60}m" for zone, seconds in enumerate(schedule.zones.seconds, 1) if seconds
    ) or "nessuna"
    return (
        f"#{schedule.number} {schedule.name or '(senza nome)'} | {schedule.cycle.name} | "
        f"giorni: {format_days(schedule.days)} | start: {starts} | zone: {zones} | "
        f"budget: {schedule.water_budget}% | pausa: {schedule.zone_pause_seconds}s"
    )


def create_schedule() -> Schedule:
    number = ask_int("Numero programma", 1, 12)
    name = input("Nome programma: ").strip()
    cycle = ProgramCycle(ask_int("Ciclo [0 custom, 1 pari, 2 dispari, 3 dispari-no31, 4 periodico]", 0, 4))
    days = Days.EVERY_DAY
    if cycle is ProgramCycle.CUSTOM:
        selected = input("Giorni [1=Lun ... 7=Dom, separati da spazio]: ").split()
        days = Days(0)
        for value in selected:
            if not value.isdigit() or not 1 <= int(value) <= 7:
                raise ValueError("giorni non validi")
            days |= DAY_OPTIONS[int(value) - 1][0]
        if not days:
            raise ValueError("seleziona almeno un giorno")
    count = ask_int("Numero partenze", 0, 8)
    starts = tuple(ask_time(f"Partenza {index}") for index in range(1, count + 1))
    durations = ZoneDurations.minutes(
        one=ask_int("Durata zona 1, minuti", 0, 279620),
        two=ask_int("Durata zona 2, minuti", 0, 279620),
        three=ask_int("Durata zona 3, minuti", 0, 279620),
        four=ask_int("Durata zona 4, minuti", 0, 279620),
    )
    water_budget = ask_int("Budget acqua, percento", 0, 65535)
    zone_pause_seconds = ask_int("Pausa tra zone, secondi", 0, 65535)
    period_length = 2
    synchronization_day = 0
    if cycle is ProgramCycle.PERIODIC:
        period_length = ask_int("Periodo, giorni", 1, 255)
        synchronization_day = ask_int("Giorno fase [0=oggi]", 0, period_length - 1)
    return Schedule(
        number=number,
        name=name,
        days=days,
        starts=starts,
        zones=durations,
        cycle=cycle,
        water_budget=water_budget,
        zone_pause_seconds=zone_pause_seconds,
        period_length=period_length,
        synchronization_day=synchronization_day,
    )


def print_status(status: object) -> None:
    print(f"Attivo: {status.enabled} | Manuale: {status.manual}")
    print(f"Zona attiva: {status.active_zone} | Secondi residui: {status.remaining_seconds}")
    print(f"Batteria raw: {status.battery_raw} | Durate zone: {status.zone_remaining_seconds}")


def is_transport_failure(error: Exception) -> bool:
    return isinstance(error, (BleakError, TimeoutError, ConnectivityError))


async def macos_rssi(client: BleakClient) -> int:
    """Read RSSI from connected CoreBluetooth peripheral."""
    if sys.platform != "darwin":
        raise RuntimeError("RSSI live supportato solo su macOS")
    read_rssi = getattr(client._backend, "get_rssi", None)
    if read_rssi is None:
        raise RuntimeError("Backend CoreBluetooth senza lettura RSSI")
    return await read_rssi()


async def connect(address: str) -> tuple[BleakClient, WooBeeV2]:
    client = BleakClient(address)
    try:
        await client.connect()
        woobee = WooBeeV2(SolemSession(client, WOOBEE_V2_GATT))
        await woobee.authenticate()
        return client, woobee
    except BaseException:
        with suppress(BleakError):
            await client.disconnect()
        raise


async def menu(address: str) -> None:
    client, woobee = await connect(address)
    try:
        while True:
            print("\n1 Stato  2 Avvia zona  3 Stop  4 Programmi  5 Salva programma")
            print("6 RSSI  7 Backup  8 Ripristina  9 Sync orologio  10 Reset fault  11 Info device  0 Esci")
            choice = input("> ").strip()
            try:
                if choice == "0":
                    return
                if choice == "1":
                    state = await woobee.read_state()
                    print_status(state.status)
                    print(f"Fault valvole: {state.valve_faults.faulty_zones or 'nessuno'}")
                elif choice == "2":
                    print_status(await woobee.start_valve(ask_int("Zona", 1, 4), ask_int("Minuti", 1, 279620)))
                elif choice == "3":
                    print_status(await woobee.stop())
                elif choice == "4":
                    for schedule in await woobee.read_schedules():
                        print(format_schedule(schedule))
                elif choice == "5":
                    schedule = create_schedule()
                    print(format_schedule(schedule))
                    if input("Scrivi SALVA per sovrascrivere programma: ") == "SALVA":
                        await woobee.write_schedule(schedule)
                        print("Programma salvato.")
                    else:
                        print("Annullato.")
                elif choice == "6":
                    print(f"RSSI: {await macos_rssi(client)} dBm")
                elif choice == "7":
                    path = Path(input("File backup JSON: ").strip()).expanduser()
                    path.write_text((await woobee.backup()).to_json() + "\n", encoding="utf-8")
                    print(f"Backup salvato: {path}")
                elif choice == "8":
                    path = Path(input("File backup JSON: ").strip()).expanduser()
                    backup = ControllerBackup.from_json(path.read_text(encoding="utf-8"))
                    print(f"Ripristino: {len(backup.schedules)} programmi da {path}")
                    if input("Scrivi RIPRISTINA per sovrascrivere programmi: ") == "RIPRISTINA":
                        await woobee.restore(backup)
                        print("Backup ripristinato.")
                    else:
                        print("Annullato.")
                elif choice == "9":
                    if input("Scrivi ORA per sincronizzare orologio controller: ") == "ORA":
                        await woobee.sync_clock()
                        print("Orologio sincronizzato.")
                    else:
                        print("Annullato.")
                elif choice == "10":
                    if input("Scrivi RESET per azzerare fault valvole: ") == "RESET":
                        print(f"Fault valvole: {(await woobee.reset_valve_faults()).faulty_zones or 'nessuno'}")
                    else:
                        print("Annullato.")
                elif choice == "11":
                    info = await woobee.read_device_info()
                    print(f"Nome: {info.name or 'n/d'} | Seriale: {info.serial or 'n/d'}")
                    print(f"Firmware: {info.firmware or 'n/d'} | Hardware: {info.hardware or 'n/d'}")
                    print(f"Indirizzo: {info.bluetooth_address or 'n/d'} | UUID: {info.uuid or 'n/d'}")
                else:
                    print("Scelta non valida.")
            except Exception as exc:
                print(f"Errore: {exc or type(exc).__name__}")
                if not is_transport_failure(exc):
                    continue
                print("Connessione BLE persa. Riconnessione...")
                with suppress(ConnectivityError):
                    await woobee.aclose()
                with suppress(BleakError):
                    await client.disconnect()
                try:
                    client, woobee = await connect(address)
                except Exception as reconnect_error:
                    print(f"Riconnessione fallita: {reconnect_error or type(reconnect_error).__name__}")
                    return
                print("Riconnesso.")
    finally:
        with suppress(ConnectivityError):
            await woobee.aclose()
        with suppress(BleakError):
            await client.disconnect()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Menu WooBee V2/WB-4")
    parser.add_argument("address", help="CoreBluetooth UUID o BLE MAC")
    args = parser.parse_args()
    await menu(args.address)


if __name__ == "__main__":
    asyncio.run(main())
