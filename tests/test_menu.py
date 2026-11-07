"""Pure formatting checks for interactive menu."""

import importlib.util
import asyncio
import unittest
from unittest.mock import patch
from pathlib import Path

from bleak.exc import BleakError

from woobee_api import Days, Schedule, TimeOfDay, ZoneDurations


MENU_PATH = Path(__file__).parents[1] / "scripts" / "woobee_menu.py"
SPEC = importlib.util.spec_from_file_location("woobee_menu", MENU_PATH)
assert SPEC and SPEC.loader
menu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(menu)


class MenuTests(unittest.TestCase):
    def test_macos_rssi_reads_connected_corebluetooth_peripheral(self) -> None:
        class Backend:
            async def get_rssi(self):
                return -63

        client = type("Client", (), {"_backend": Backend()})()
        with patch.object(menu.sys, "platform", "darwin"):
            self.assertEqual(-63, asyncio.run(menu.macos_rssi(client)))

    def test_transport_failure_requires_reconnect(self) -> None:
        self.assertTrue(menu.is_transport_failure(TimeoutError()))
        self.assertTrue(menu.is_transport_failure(BleakError("Service Discovery has not been performed yet")))
        self.assertFalse(menu.is_transport_failure(ValueError("bad input")))

    def test_format_schedule_uses_human_domain_values(self) -> None:
        schedule = Schedule(
            number=1,
            name="Giardino",
            days=Days.MONDAY | Days.WEDNESDAY,
            starts=(TimeOfDay(7),),
            zones=ZoneDurations.minutes(one=10, three=5),
        )

        self.assertEqual(
            menu.format_schedule(schedule),
            "#1 Giardino | CUSTOM | giorni: Lun, Mer | start: 07:00 | zone: Z1=10m, Z3=5m | budget: 100% | pausa: 0s",
        )

