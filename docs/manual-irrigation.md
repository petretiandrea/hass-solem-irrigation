# Manual irrigation (SBR-94)

## Platform and protocol boundary

Use the **button** platform: these are timed, momentary commands, not a retained
switch state. Four start buttons run their zone for **one minute** on press.
One controller button stops **all irrigation**, including a run started outside
HA. There is no confirmed per-zone stop opcode. A switch/valve per zone would
suggest an independently closable output and hide the global stop side effect.
Existing read entities remain the source of reported activity and countdown.
All five buttons share the controller device, translated names and stable IDs.

The entity action `solem_woobee.start_irrigation` targets a **start button** and
requires `minutes`: a strict integer in **1–279620**, inclusive. Booleans,
fractional values and strings are rejected. The client multiplies by 60 and
encodes seconds in 24 bits (`WooBeeV2.start_valve_frame`, command 0x31/0x12).
The maximum is a wire-format limit, not a verified safe watering recommendation
or a confirmed firmware/UI limit. Use short supervised runs until validated on
your device. No duration helper is persisted and no program APIs are exposed.

Example (replace entity ID using your entity picker):

```yaml
action: solem_woobee.start_irrigation
target:
  entity_id: button.garden_start_zone_1_1_minute
data:
  minutes: 2
```

Use `button.press` on **Stop all irrigation** to stop any running zone. Do not
target several start buttons together; only one active zone is supported.

## Consistency and errors

Every command opens a fresh authenticated BLE session. One per-entry lock
serializes commands with polling. Before a start, a fresh state read must report
no active zone. Any active zone (including the requested one) rejects the start
without writing, to avoid restarting/extending a run or replacing another zone.
Another application can still race HA; exclusive control cannot be guaranteed.
Stop does not depend on a pre-read or a particular active zone.

After a single command transmission, HA performs a full state read in the same
session and publishes that observation for all entities. Start is confirmed only
when the requested zone is reported active; stop only when no WB-4 zone is
reported active. A mismatched result raises an action error while preserving the
observed state. There is no documented eventual-consistency interval or decoded
command-rejection code: rejection and delayed application are therefore reported
as **unconfirmed**, not as successful. No optimistic on/off state is written.

Offline, authentication, malformed-response and timeout failures raise an HA
action error and mark the coordinator unavailable. A timeout can occur after
hardware applied a command: the outcome is unknown, not proof that watering
stopped. No command is automatically retried. The next normal five-minute poll
(or an explicit entity refresh) reads state safely and restores availability.
Check the physical controller before manually resending an ambiguous command.
HA records a button timestamp when a press is attempted, before the handler runs;
it is not a success indicator. Only a completed action without error and the
reported activity entities provide command/state confirmation, not measured flow.
The duration action does not change the button press timestamp.

## Supervised device verification (not executed by the agent)

Only run these steps with explicit authorization for actuator commands, physical
access and a safe water supply/drainage arrangement. Record hardware model,
firmware, HA version, timestamps, observed states, and physical behavior without
publishing BLE identity or raw frames.

1. Use the confirmed WB-4 firmware 7.0.2; close MySOLEM, establish HA Bluetooth
   reachability and confirm idle status. Check all entity device associations.
2. Press each zone's one-minute start button in turn. Verify the intended valve
   physically opens, HA reports that zone active and the countdown is in seconds.
   Stop with the controller stop button between zones; verify all valves close.
3. Run the duration action with 2 minutes; observe automatic completion. Check
   0, negative, fractional, string, bool and 279621 durations are rejected before
   BLE writes. Do not physically test the wire maximum as a long watering run.
4. While a zone runs, attempt the same zone and another zone: HA must reject both
   without restarting, extending or replacing the run. Stop, then start the next.
5. Start a short run in MySOLEM, disconnect it, then use HA's global stop. Verify
   its side effect is correctly labelled and the physical valve closes.
6. With no active watering, make the controller unreachable and attempt a
   command: expect an action error; the button timestamp only records the attempt. Restore
   reachability and refresh; verify recovery. Simulate timeout/rejection in tests
   rather than deliberately losing control during physical watering.
7. Record command-to-state latency. If firmware needs settling time, document it
   before adding bounded **read-only** verification polling; never retry starts.
8. Reload/unload the integration and verify buttons return with stable registry
   IDs and polling stops on unload. Finish with the controller physically idle.

Automated evidence: `tests/integration/test_commands.py` uses a simulated client
for routing, durations, conflicts, offline/auth/timeout/invalid replies,
unconfirmed outcomes, no retries, session cleanup and poll serialization.

Sources reviewed:
- https://contributors.home-assistant.io/core/entities/button/
- https://contributors.home-assistant.io/core/integrations/actions/
- https://contributors.home-assistant.io/core/quality-scale/
- Existing client protocol and README reverse-engineering evidence (SBR-88).
