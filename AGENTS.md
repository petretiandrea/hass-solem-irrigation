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

- Use Python 3.14 for the client, integration and CI (`.python-version`).
- Keep Python imports at module top level, never inside functions or methods.

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

## Home Assistant quality

The Home Assistant Integration Quality Scale must guide design, implementation
and review for every integration task, including work tracked in Linear. Review
the applicable official rules before implementing a change:
https://contributors.home-assistant.io/core/quality-scale/.

Use `custom_components/solem_woobee/quality_scale.yaml` and
`docs/quality-scale.md` as acceptance criteria. For each affected rule, implement
the requirement and record concrete evidence (code, tests or documentation), or
document a justified exemption. Keep unresolved requirements explicitly TODO;
do not mark rules done merely because tests pass or a base class is used.
Update the checklist and review evidence in the same PR as the behavior change.
PR descriptions and Linear completion updates must identify applicable checks
and remaining gaps. Do not claim a tier while its required rules remain TODO.

Preserve unknown values as None and let real entity subscriptions own
coordinator polling. New platforms must verify actual HA states, registry IDs,
device association, translations, metadata and unload behavior. Run the HA
integration tests and the per-module coverage gate described in
`docs/quality-scale.md` for changes to the HA adapter.

## Verify

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q custom_components scripts tests
```

Run hardware commands manually after tests. BLE timeouts can invalidate macOS
service discovery; menu reconnects and authenticates again after `TimeoutError`
or `BleakError`.
