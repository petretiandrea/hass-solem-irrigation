#!/usr/bin/env python3
"""Verify MySOLEM-compatible WooBee authentication without actuator commands."""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient

from solem_woobee import SolemSession, WOOBEE_V2_GATT


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", help="CoreBluetooth UUID printed by inspect_woobee.py")
    args = parser.parse_args()

    print(f"Authenticating {args.address}; no valve frame is sent.")
    async with BleakClient(args.address) as client:
        session = SolemSession(client, WOOBEE_V2_GATT)
        await session.authenticate()
    print("Authenticated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
