# WooBee V2 agent handoff

## Scope

Python BLE client for SOLEM WooBee V2 / WB-4 firmware 7.0.2. Protocol facts
come from static reverse engineering of MySOLEM 6.13.3; see `README.md` for
frames and `docs/research/` for integration research.

## Safety boundary

`inspect_woobee.py`, `read_*()` and `backup()` are read-only.
`WooBeeV2.start_*()`, `stop()`, `write_program()`, `write_schedule()`,
`restore()`, `sync_clock()` and `reset_valve_faults()` change controller state.
Do not run them against hardware unless user explicitly asks for that command.

## Design

- `Schedule`, `Days`, `TimeOfDay`, `ZoneDurations`: public domain API.
- `IrrigationProgram`: internal wire model; zero-based index, eight starts,
  duration seconds. Keep wire padding out of public APIs.
- `ControllerBackup`: portable JSON for this client, not MySOLEM export format.
- `SolemSession`: authentication, AES and notification transport.
- `WooBeeV2`: recovered commands and response parsing boundary.
- `scripts/woobee_menu.py`: interactive client. Menu item `6` reads connected
  RSSI via CoreBluetooth on macOS; it intentionally uses Bleak's macOS backend
  because generic Bleak exposes no RSSI API.

## Hardware evidence

Confirmed device: WB-4, type 180, firmware 7.0.2. GATT family:
`A98C0002-53E4-441C-96AF-B318E57E3B91`; response `0003`; auth `0005`.
Do not generalize protocol support to other SOLEM product types without APK or
hardware evidence.

## Verify

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q solem_woobee scripts tests
```

Run hardware commands manually after tests. BLE timeouts can invalidate macOS
service discovery; menu reconnects and authenticates again after `TimeoutError`
or `BleakError`.
