# Quality Scale review

The Quality Scale guides implementation and review. No official tier is claimed
for this custom integration. `custom_components/solem_woobee/quality_scale.yaml`
tracks every rule with evidence, pending work or an explicit exemption reason.
Do not mark a rule done solely because a base class exists or tests pass.

Sources reviewed:
- https://contributors.home-assistant.io/core/quality-scale/
- https://contributors.home-assistant.io/core/quality-scale/quality-scale-file/
- https://contributors.home-assistant.io/core/quality-scale/entity-unavailable/
- https://contributors.home-assistant.io/core/integrations/fetching-data/

## SBR-92 corrections

| Finding | Resolution and evidence |
| --- | --- |
| Missing duration made the entire zone unavailable | Zone availability inherits CoordinatorEntity. `remaining_seconds` preserves None; tests distinguish missing data from zero and connection failure. Final platform state properties must preserve None. |
| Synthetic listener polled without consumers | Removed. EntityComponent lifecycle test verifies no timer polling before subscription, polling while subscribed, stopping after removal and successful unload. |
| README described the pre-coordinator skeleton | Updated polling behavior, scope and removal instructions. |
| Coverage had no gate | CI reports line/branch coverage and requires >95% for each HA adapter module, including entity.py and config flow. |

## Remaining acceptance work

Bronze is not claimed: branding and dependency provenance remain to be reviewed,
and hardware command-platform behavior remains to be verified. The embedded
client is an intentional custom-integration architecture decision, not a claimed
exemption from Core distribution requirements.

Silver is not claimed: the HA adapter coverage gate excludes `woobee_api`, whose
unit tests run separately. The whole-integration coverage requirement remains
TODO until every embedded module is assessed along with the final platforms.
Command errors are covered by SBR-94 simulations. Read platforms
explicitly declare parallel update behavior. Fixed-key BLE has no user credentials or reauthentication flow; that
exemption is documented rather than inventing a cloud login.

Gold/Platinum work (verified discovery, exception translations,
strict typing and lifecycle configuration flows) remains visible in the checklist.
Five-minute polling is a documented conservative choice, not a measured battery
or BLE limit. Hardware tests are still needed for battery impact and freshness.

## Validation

Use the project's Python 3.14 environment:

```bash
python -m unittest discover -s tests -v
python -m pytest tests/integration -q --cov=custom_components.solem_woobee --cov-branch --cov-report=term-missing --cov-report=json
python scripts/check_ha_coverage.py
python -m compileall -q custom_components scripts tests
```

CI runs integration checks against HA 2026.8.0 and 2026.10.4. Every future platform
must extend lifecycle/state tests and update this checklist with evidence.

## SBR-93 read entities

The sensor/binary_sensor platforms follow the Sorgenia template's entity
descriptions, translations and explicit parallel-update declaration, while
consuming the existing WooBee coordinator. Only client-decoded fields are
exposed; the README documents every mapping and intentional omission.

`tests/integration/test_entities.py` validates actual HA states, English/Italian
names, registry IDs/device association, diagnostic categories, disabled raw
battery enablement, shared reads, failure/recovery, reload and polling teardown.
The countdown has a duration device class and seconds unit but no statistics
state class: it is a controller countdown, not accumulated irrigation usage.
Raw battery has no inferred percentage or voltage; input-open does not imply rain.

Reference: https://contributors.home-assistant.io/core/entities/naming/ and
https://developers.home-assistant.io/docs/core/entity/sensor/.
Read platform coverage is included in the existing per-module CI gate. No
hardware validation or official Quality Scale tier is claimed.

## Follow-up Quality Scale review

Reviewed the official entity-disabled-by-default, icon-translations and
log-when-unavailable rules. Raw battery remains disabled by default because its
unverified scale is useful for investigation. Zone activity/duration, operational
flags and fault/connectivity diagnostics remain enabled for monitoring and alerts.
Countdowns update only on the shared five-minute read, with no per-second noise.

Added icons.json for fields without a fitting device class; existing device-class
icons remain supplied by HA. Added a regression test for one failure log across
repeated failed reads and one recovery log across repeated successes. README now
includes dashboard and fault-notification examples and troubleshooting steps.

Sources:
- https://contributors.home-assistant.io/core/quality-scale/entity-disabled-by-default/
- https://contributors.home-assistant.io/core/quality-scale/icon-translations/
- https://contributors.home-assistant.io/core/quality-scale/log-when-unavailable/

The checklist records these rules individually. The adapter coverage gate does
not establish whole-integration Silver compliance; branding, library provenance,
embedded-client coverage and remaining checklist items still prevent a tier claim.

## SBR-94 manual commands

Four water valves expose OPEN/CLOSE with controller-reported open/closed state,
without position or motion controls. Timed opening uses a per-zone default saved
in HA options (initially one minute); an entity action can override a single run.
Conditional close reads fresh state under the shared command/poll lock and sends
the global stop only for the active target zone. Idle/different zone closure is a
read-only no-op. An explicit controller-wide stop button remains available.
The external-client race between read and global stop is documented rather than
claiming an atomic per-zone protocol capability.

Affected rules and evidence:
- action-setup/docs-actions: actions registered during integration async_setup;
  schema/services.yaml and HA selector validation tested. Manual-irrigation docs
  include units, limits, defaults/persistence, examples and guarded-close behavior.
- action-exceptions/parallel-updates: simulated client tests cover validation,
  conflicts, conditional/global stop, transport/auth/timeout/invalid responses,
  mismatched outcomes, cancellation and polling serialization. No optimistic
  success or command retries; failed commands surface HA errors.
- entity naming/unique IDs/devices/device classes/translations/availability:
  actual HA states, water class, supported flags, en/it names, shared controller,
  reload/unload, disabled raw sensor and failure/recovery tests include valves.
- entity-event-setup/config-entry-unloading/test-coverage: actual entity listeners
  own polling; lifecycle tests cover teardown. The per-module adapter coverage
  gate includes valve.py and services.py. No whole-client coverage claim.
- docs-configuration-parameters: per-zone local default duration documented, with
  persistence and temporary overrides tested. No controller program writes.

`docs/manual-irrigation.md` records supervised hardware verification and migration
from the earlier PR's start buttons to valves. No hardware tests have been run;
firmware latency, physical behavior, maximum practical duration and battery
impact remain unverified. Existing branding, dependency provenance, whole-client
coverage, diagnostics, exception translations and strict typing TODOs remain.
No Quality Scale tier is claimed.

Official sources reviewed: valve entity, integration actions and Quality Scale
contributor documentation. HA target-selector metadata is validated with HA's
schema, including a regression against the earlier invalid numeric feature
filter. Official hassfest is also run locally; remote checks may remain unreadable
to the GitHub App (403), so local success does not assert a remote CI result.

Valve-platform validation: Python 3.14.10, 77 integration tests passed on each
of HA 2026.8.0/plugin 0.13.354 and HA 2026.10.4/plugin 0.13.375. Line/branch
coverage is 100% in each of 13 adapter modules, and the >95% per-module gate
passes. All 34 client unittests, compileall and git diff --check pass. The full
official hassfest validator (Core f8cdb14) reports 1 integration, 0 invalid.
HA 2026.8.0 emits pytest-socket warnings from Bluetooth setup without failures.

## SBR-95 diagnostics and cross-cutting tests

Reviewed official [diagnostics](https://contributors.home-assistant.io/core/quality-scale/diagnostics/),
[log-when-unavailable](https://contributors.home-assistant.io/core/quality-scale/log-when-unavailable/)
and [test-coverage](https://contributors.home-assistant.io/core/quality-scale/test-coverage/)
rules. `diagnostics.py` uses an explicit allowlist of cached operational fields;
no entry serialization, identities, raw frames or session/credential objects are
exported. It makes no BLE requests. `test_diagnostics.py` covers the actual HA
HTTP download, sensitive synthetic fields, missing data and stale/empty snapshots.
The diagnostics rule is done independently of discovery, which remains TODO.

`test_privacy.py` verifies secret-bearing auth, connectivity, invalid-response and
timeout errors at DEBUG, one outage/recovery log, sanitized command tracebacks,
and successful fresh-session recovery on the next poll after authentication
rejection. Outward errors explicitly chain anonymized client exceptions, retaining
known client types, traceback locations and cause/context links while removing
arbitrary messages, notes and custom attributes. Existing flow/lifecycle/entity/
command tests continue
to cover the complete HA surface; all fixtures and BLE failures are simulated.
No cloud token expiry flow is applicable to this fixed-key BLE integration.

`docs/diagnostics-and-validation.md` maps automated evidence to acceptance criteria
and provides a supervised WB-4 procedure, including anonymous downloads, offline
and recovery checks, physical zone validation and a pending hardware report.
This updates diagnostics, troubleshooting, known-limitations, availability/logging,
action-exceptions, config-flow-test-coverage, unloading and test-coverage evidence.
No hardware was accessed for this task. Whole-client coverage, branding, dependency
provenance, discovery, exception translations, strict typing and other existing
TODOs remain; no official tier is claimed.

SBR-95 validation: Python 3.14.10; 90 HA integration tests passed on each of
HA 2026.8.0/plugin 0.13.354 and HA 2026.10.4/plugin 0.13.375. All 14 HA adapter
modules have 100% line/branch coverage; the >95% per-module gate passes. All
34 client unittests, compileall and git diff --check pass. Full official hassfest
from Core tag 2026.10.4 (357cae5) reports 1 integration, 0 invalid integrations.
HA 2026.8.0 emits 54 pytest-socket warnings during mocked Bluetooth setup; no
tests fail and no real hardware is used. Local checks do not assert remote CI
success. The integration-only coverage run reports 54% overall including the
embedded client: it is not evidence of whole-integration Silver compliance.

The Sorgenia template's `async_get_config_entry_diagnostics` entry point and
coordinator runtime pattern were checked directly. WooBee uses an operational
field allowlist instead of serializing/redacting whole entry data and arbitrary
exception strings, so new identity/session fields remain excluded by default.


### SBR-95 PR review: retain underlying errors

Replaced all three coordinator `from None` sites (authentication/read failures
and command failures) with explicit anonymized exception causes. Known client
exception types and their original traceback locations remain visible. Nested
transport errors retain class names and traceback locations; causal/context
links and suppression semantics survive, including shared/cyclic links. Messages,
notes and custom attributes are omitted because they can carry identifiers or
credentials. The original exception is never mutated. No raw exception text is
logged as a fallback.

`test_privacy.py` verifies read and command causes for auth/connectivity/response/
session-timeout/timeout failures, nested explicit and implicit transport failures,
traceback identity, notes/filename redaction, cycle handling and unchanged original
exceptions. The existing DEBUG outage/recovery tests still enforce private logs.
Applicable rules remain action-exceptions, log-when-unavailable and test-coverage;
previous checklist TODOs and hardware limitations are unchanged.

Review validation: 100 integration tests pass on each of HA 2026.10.4 and
2026.8.0 with Python 3.14.10; all 14 adapter modules retain 100% line/branch
coverage and pass the >95% per-module gate. All 34 client unittests, compileall,
git diff --check and full official hassfest (Core 2026.10.4: 1 integration,
0 invalid) pass. The older HA version still emits the same 54 mocked-Bluetooth
pytest-socket warnings. The integration-only coverage run is now 55% overall;
whole-client coverage and hardware validation remain pending, with no tier claim.
