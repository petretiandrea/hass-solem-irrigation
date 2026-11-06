#!/usr/bin/env python3
"""Discover and inspect a WooBee BLE controller without writing to it."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from solem_woobee import WooBeeClient


def select_device(devices: list[object]) -> object:
    if len(devices) == 1:
        return devices[0]
    for index, device in enumerate(devices, start=1):
        print(f"[{index}] {device}")
    while True:
        try:
            return devices[int(input("WooBee number: ")) - 1]
        except (IndexError, ValueError):
            print(f"Choose 1-{len(devices)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", help="Skip scan and inspect this BLE MAC address")
    parser.add_argument("--timeout", type=float, default=15, help="Scan duration in seconds")
    parser.add_argument("--output", type=Path, default=Path("woobee-gatt.json"))
    args = parser.parse_args()

    client = WooBeeClient.local()
    address = args.address
    if not address:
        print(f"Scanning for {args.timeout:g}s. Keep MySOLEM closed.")
        devices = await client.discover(args.timeout)
        if not devices:
            raise SystemExit("No BLE devices found. Move closer, then retry.")
        address = select_device(devices).address

    print(f"Inspecting {address}; read-only, no valve command is sent.")
    profile = await client.inspect(address)
    payload = asdict(profile)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
