"""MySOLEM-equivalent WooBee V2 manual control from static APK reverse engineering."""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient

from solem_woobee import SolemSession, WOOBEE_V2_GATT, WooBeeV2


def print_status(status: object) -> None:
    print(f"enabled: {status.enabled}")
    print(f"manual: {status.manual}")
    print(f"active_zone: {status.active_zone}")
    print(f"remaining_seconds: {status.remaining_seconds}")
    print(f"zone_remaining_seconds: {status.zone_remaining_seconds}")
    print(f"battery_raw: {status.battery_raw}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("address", help="CoreBluetooth UUID or BLE MAC address")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    start = commands.add_parser("start")
    start.add_argument("zone", type=int, choices=range(1, 5))
    start.add_argument("minutes", type=int)
    commands.add_parser("stop")
    all_valves = commands.add_parser("start-all")
    all_valves.add_argument("minutes", type=int)
    program = commands.add_parser("start-program")
    program.add_argument("program", type=int)
    args = parser.parse_args()

    async with BleakClient(args.address) as client:
        woobee = WooBeeV2(SolemSession(client, WOOBEE_V2_GATT))
        await woobee.authenticate()
        if args.command == "status":
            state = await woobee.read_state()
            print_status(state.status)
            print(f"faulty_zones: {state.valve_faults.faulty_zones}")
        elif args.command == "start":
            print_status(await woobee.start_valve(args.zone, args.minutes))
        elif args.command == "stop":
            print_status(await woobee.stop())
        elif args.command == "start-all":
            print_status(await woobee.start_all(args.minutes))
        else:
            print_status(await woobee.start_program(args.program))


if __name__ == "__main__":
    asyncio.run(main())
