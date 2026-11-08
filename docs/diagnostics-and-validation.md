# Diagnostics and validation

## Download diagnostics

In Home Assistant, open Settings → Devices & services → SOLEM WooBee → entry
menu → Download diagnostics. The integration section contains only cached
operational values: last-read success, polling interval, controller flags, raw
battery value (not a percentage), active program/zone, remaining seconds and
faulty zone numbers. It performs no Bluetooth I/O or commands. A failed read
retains the last snapshot with `last_update_success: false`; missing durations
remain JSON null, distinct from zero. Before the first snapshot it returns null.

The export deliberately excludes all config entry data/options/title/IDs, BLE
MAC/CoreBluetooth address, device name, serial, UUID, raw identity/state/alert
frames, credentials, tokens, fixed protocol keys, challenges and session objects.
An explicit field allowlist also excludes future unknown configuration fields.
No pseudonym or hash permits linking controllers across exports. HA may add its
own system metadata around the integration payload; inspect the complete download
before publishing it. The unscaled battery field is retained for troubleshooting.

Poll errors distinguish authentication rejection from transport/invalid-response
failure; check Bluetooth reachability, connection slots and response completeness.
The coordinator logs one outage and one recovery, without repeating each failed
poll. Each new poll authenticates a new session. The fixed-key local BLE protocol
has no cloud account, expiring token or user credential reauth flow. Command
errors are surfaced to the caller;
unknown outcomes must be checked on the device before another command is sent.
Poll and command errors explicitly chain the original client exception using
`raise ... from exc`. Exception messages, notes, attributes and nested causes are
preserved for troubleshooting; exceptions are not anonymized. HA DEBUG logs
include the original exception traceback. Integration-owned
availability messages do not interpolate client error text. Anonymization applies
to the downloadable diagnostics payload described above.


## Automated tests

All addresses, names, nonces and frames in tests are synthetic. No live account,
captured private payload or real controller identifier is required. Tests use
real HA setup/services/states/registries with mocked BLE/client boundaries:

| Scope | Evidence |
| --- | --- |
| Configuration, duplicate entries, auth/transport/response failures | `test_config_flow.py` |
| Setup retry, unload/reload, BLE resource closure | `test_init.py` |
| Shared polling, unknown/zero data, offline/recovery, listener teardown | `test_coordinator.py`, `test_entities.py` |
| Entity states, metadata, translations, identity stability | `test_entities.py`, `test_commands.py` |
| Commands, timeouts, rejected auth, serialization, no replay, recovery | `test_commands.py` |
| Availability messages at DEBUG and original command exception causes; fresh scope after session rejection | `test_errors.py` |
| Anonymous cached diagnostics, stale/empty/partial snapshots, no I/O | `test_diagnostics.py` |
| Real protocol parsing, fresh handshake and cleanup over fake BLE | `tests/test_session.py`, `tests/test_client.py` |

Run the [quality checks](quality-scale.md); the combined coverage gate includes
the adapter and embedded client.

## Hardware validation

Use WB-4 firmware 7.0.2; do not infer other product support. Record date, tester,
HA/Python/integration version, adapter/proxy type, firmware, expected/observed
result and pass/fail for every step. Use anonymous controller/zone labels; keep
hardware identifiers outside the published report.

1. Close MySOLEM, confirm HA BLE reachability and configure the controller. Check
   one controller device and four zone valves with expected read entities.
2. Download diagnostics while idle and compare numeric/boolean values with HA.
   Search the whole downloaded JSON for the actual name, MAC (all forms), serial,
   UUID and known personal labels. Confirm none occurs in the integration payload;
   record any HA envelope disclosure separately. Check logs at INFO and DEBUG.
3. Perform the explicitly authorized, supervised zone procedure in
   [manual-irrigation.md](manual-irrigation.md#supervised-device-verification).
   Check every real zone, default/override duration, conditional close, global stop
   and physical timed completion. Report controller state versus physical water
   behavior separately; HA does not measure flow.
4. With all watering stopped, make BLE unreachable. Wait for a poll: entities
   become unavailable and one failure appears. Download diagnostics: cached
   values remain, success is false, and identifiers are absent. Keep unreachable
   for another poll and check no duplicate outage log.
5. Restore reachability; next poll must reconnect/authenticate, restore entity
   availability and log recovery once. Download diagnostics again. Do not induce
   loss of control during irrigation. Session rejection, malformed/partial frames
   and post-write timeout are deliberately simulated, not forced on hardware.
6. Reload, confirm stable registry associations, unload and verify no further
   polling. End with all physical valves idle. Do not publish raw BLE backups.

Hardware validation remains pending. BLE range, battery impact, command latency
and physical valve behavior need a supervised report. Record expected and
observed results for each step; simulated tests do not satisfy those checks.
