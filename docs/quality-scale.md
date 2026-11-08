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

`test_errors.py` verifies auth, connectivity, invalid-response and timeout errors,
one outage/recovery log and successful fresh-session recovery on the next poll
after authentication rejection. Poll and command failures explicitly chain the
original exception with `raise ... from exc`, preserving its messages, notes,
attributes, traceback and nested causes. Exceptions are not anonymized.
Integration-owned availability messages do not interpolate client error text.
Existing flow/lifecycle/entity/command tests cover the complete HA surface; all
fixtures and BLE failures are simulated. No cloud token expiry flow applies.

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


### SBR-95 PR review: original exception causes

Per review clarification, exception anonymization is out of scope. Removed the
exception-copy helper and chain the original client exceptions in all three
coordinator handlers with `from exc`. Downloadable diagnostics retain their
operational allowlist. `test_errors.py` checks original cause identity and
unmodified nested causes, messages and notes for read/command failures, as well
as availability logging and fresh-session recovery. Applicable rules remain
action-exceptions, log-when-unavailable and test-coverage. Existing Quality Scale
TODOs and hardware limitations remain unchanged.

Validation after removing exception anonymization: 99 integration tests pass on
both HA 2026.10.4 and 2026.8.0 with Python 3.14.10. All 14 adapter modules have
100% line/branch coverage and pass the >95% per-module gate. All 34 client tests,
compileall, git diff --check and full official hassfest (1 integration, 0 invalid)
pass. HA 2026.8.0 retains 54 mocked-Bluetooth pytest-socket warnings. No hardware
validation or additional Quality Scale tier is claimed.

## SBR-96 distribution and documentation

Reviewed the official Quality Scale documentation rules and directly inspected
hass-sorgenia metadata and validation/release workflows. README now leads with
HA/HACS/manual installation, prerequisites, verified device scope, actual local
BLE/cloud dependency, configuration and links to entity/action/automation docs.
`docs/releasing.md` defines the sole manifest-based version process, no PyPI,
manual draft/release steps and an explicitly pending fresh-install/hardware
checklist. Merging this PR does not create or publish a release.

Affected rules: docs-high-level-description, docs-installation-instructions,
docs-installation-parameters, docs-configuration-parameters, docs-removal-instructions,
docs-supported-devices/functions, docs-known-limitations, docs-data-update,
docs-actions/examples/use-cases/troubleshooting. Evidence is in README and the
linked manual-command, diagnostics and release documents. Dependency transparency
remains TODO for licensing/provenance/Core packaging review; the embedded client
is documented, not declared exempt. Brands remains TODO; HACS explicitly ignores
only that check, following the reference template. No tier is claimed.

CI retains both HA targets and the >95% per-module adapter coverage gate, adds
Ruff fatal-error checks and a source-layout/import/metadata gate, and runs HACS
alongside hassfest. No adapter behavior changes. Whole-client coverage, branding,
provenance, discovery, translations of exceptions, strict typing and the remaining
checklist TODOs are still open. Clean-install and real-hardware evidence must be
collected before the first release; simulated tests do not close those gaps.

Distribution review also found no LICENSE file or GitHub-detected license.
Release checklist explicitly requires a maintainer licensing/provenance decision
before distribution; no license grant is invented by this PR.

SBR-96 local validation: Python 3.14.10; Ruff 0.14.3, distribution metadata/import
gate (including matching release tag), 34 standalone client tests, compileall
and git diff --check pass. Each HA target (2026.8.0/plugin 0.13.354 and
2026.10.4/plugin 0.13.375) passes 99 integration tests; all 14 adapter modules
have 100% line/branch coverage and pass the >95% gate. HA 2026.8.0 retains 54
mocked-Bluetooth pytest-socket warnings. These results do not prove hardware,
fresh-install, HACS download or whole-integration Quality Scale compliance.
Full official hassfest from Core tag 2026.10.4 (357cae5) also passes locally:
1 integration, 0 invalid integrations. Remote HACS validation remains a CI check;
its brands exception is explicit and does not close the branding TODO.
GitHub Actions run/check status could not be read by this session: GitHub App
returns HTTP 403 / Resource not accessible by integration. A maintainer must
review the remote jobs (especially HACS) before merging; local checks are not a
claim that the remote workflow passed.

### SBR-96 HACS CI follow-up

The failing HACS job 128420133546 is now readable: it reports three failures,
missing repository topics, description and license. Integration manifest and
hacs.json validation passed; integration categories produces a warning only.
Attempts to set description/topics through the GitHub API returned HTTP 403
(Resource not accessible by integration): repository-administration access is
not granted to this session. `docs/releasing.md` supplies the exact maintainer
command. License selection is awaiting the repository owner's instruction.
These checks remain enabled; no additional HACS ignores or Quality Scale tier
claims are introduced. HACS remains failing until those prerequisites are met.

### Owner-authorized license selection

The owner delegated license selection. Added the standard MIT LICENSE for both
integration and embedded client, consistent with hass-sorgenia, plus SPDX metadata
and license-file inclusion in pyproject.toml and a README link. This resolves the
missing source license; GitHub/HACS detection must be confirmed after merge.
Repository description/topics still require administration permission (prior API
attempts returned HTTP 403). Dependency/protocol provenance and the remaining
Quality Scale TODOs remain open; no tier is claimed. No release is published.

## SBR-100 branding and provenance audit

See [the dated audit and evidence](dependency-provenance.md) for upstream asset
revision/checksums, prepared local custom-integration branding, HA dependency
versions/licenses/tags/public build paths, MySOLEM derivation blockers and a
separate Core packaging proposal. Brands and dependency-transparency remain TODO;
embedding is not an exemption. The MIT source license exists. Fresh main HACS
run 42379421457 passes with the brands ignore; description/topics/license failures
from SBR-96 are resolved. Installed branding and candidate checks remain pending.
No release, hardware command or official tier is authorized by this audit.

## SBR-101 address reconfiguration and discovery evidence blocker

Reviewed the official [discovery](https://contributors.home-assistant.io/core/quality-scale/discovery/),
[discovery-update-info](https://contributors.home-assistant.io/core/quality-scale/discovery-update-info/)
and [reconfiguration-flow](https://contributors.home-assistant.io/core/quality-scale/reconfiguration-flow/)
rules. This change implements the independently testable reconfiguration portion;
SBR-101's verified discovery acceptance remains incomplete.

`config_flow_handler.async_step_reconfigure` validates MAC/CoreBluetooth input,
requires confirmation and an authenticated read snapshot, and compares the
candidate serial against the original device registry serial. Missing original
identity fails closed; missing/mismatched candidate serials also fail. Collisions
against other entries' connection and frozen identity addresses are checked
before and after the asynchronous read. Authentication, connectivity, timeout,
invalid responses, malformed input, cancellation and collision errors preserve
entry data and allow retry where appropriate. EN/IT form/error text is included.

Identity migration is explicit: freeze the original address in additive entry
field `identity_address` on first successful reconfiguration, leave config-entry
unique ID unchanged, and use that frozen address for every platform's entity
unique ID and device identifier. Only the BLE transport uses the new `address`.
Entries without the field retain their previous identity calculation. No serial
ID conversion or registry rewrite is performed. Both old identity and current
connection addresses remain reserved against duplicate user configuration.

`tests/integration/test_reconfigure.py` exercises the actual HA flow manager,
update/reload, all error paths and retry, known/missing/mismatched serials,
cancellation, collisions arising during validation, repeated address changes,
options preservation, all 23 entity registry records/device association, user
device naming, old coordinator shutdown and successful unload with no later
polling. `test_config_flow.py` additionally verifies duplicate user setup at
both the old and new addresses, unrelated entries and a validation-time race.
Affected rules: reconfiguration-flow, config-flow-test-coverage,
unique-config-entry, entity-unique-id, devices and config-entry-unloading.

`docs/bluetooth-discovery.md` records the external evidence blocker and supplies
a supervised advertisement-only collection procedure. No raw verified WB-4
advertisement/capture provenance is in the checkout; the historical research
reference to a bugreport is insufficient to select a matcher. GATT evidence
for WB-4/type 180/firmware 7.0.2 does not establish advertised service UUIDs or
stable identity fields. No other SOLEM product support is inferred. Discovery
and discovery-update-info remain TODO with concrete reasons in the checklist.
No Bluetooth matcher/automatic update is enabled, hardware accessed or controller
writes performed. Missing capture evidence prevents completing SBR-101; no
Quality Scale tier is claimed and all unrelated TODOs remain.

SBR-101 local validation: Python 3.14.10; **118 integration tests pass on each**
of HA 2026.8.0/plugin 0.13.354 and HA 2026.10.4/plugin 0.13.375. All 14 HA adapter
modules, including the complete flow handler, have **100% line/branch coverage**;
the unchanged >95% per-module gate passes on each target. HA 2026.8.0 emits
73 pytest-socket warnings during mocked Bluetooth setup; no tests fail. All
34 standalone client unittests, Ruff 0.14.3, distribution/import validation,
compileall and git diff --check pass. Existing HA matrix, simulated BLE tests
and coverage scope are unchanged. Integration-only overall coverage remains
56% including the embedded client; this is not whole-integration Silver evidence.

Full official hassfest from Core tag 2026.10.4 (`357cae5`), with its required
Ruff 0.16.9 tooling, also passes locally: 1 integration, 0 invalid integrations.
Local validation does not assert remote CI success.

## SBR-102 translated errors and lifecycle review

Reviewed separately on 2026-11-07:
- [exception-translations](https://contributors.home-assistant.io/core/quality-scale/exception-translations/):
  coordinator poll/action errors and duration validation now use domain/key
  metadata. strings.json and en/it contain matching exception keys and numeric
  limit placeholders. Client text is not inserted into translations; original
  ValueError/transport causes remain chained unchanged. Diagnostics allowlisting,
  command locking, guarded close and no-retry behavior are preserved.
- [repair-issues](https://contributors.home-assistant.io/core/quality-scale/repair-issues/):
  exempt for the currently supported surface. There is no user account, renewable
  credential, known minimum firmware requirement, deprecated configuration or
  migration needing user confirmation. Reachability, authentication and malformed
  responses cannot establish a specific required user repair; fresh sessions
  already permit recovery. Valve fault bits are exposed as diagnostic entities,
  but the protocol evidence does not establish a safe user repair/reset procedure.
  Raw battery has no verified low-battery threshold. Do not invent firmware,
  battery or fault repairs from these signals. Revisit if a verified actionable
  condition becomes supported. Creation/resolution tests are inapplicable because
  no repair is created; lifecycle tests assert no issues during outage/recovery.
- [stale-devices](https://contributors.home-assistant.io/core/quality-scale/stale-devices/):
  the official single fixed device per config entry exemption applies. WB-4's
  four zones are fixed entities on that controller, not independently removable
  hardware. BLE silence is not proof of removal. Keep the controller during an
  outage; the user removes the integration entry to remove it and all associated
  entities. No device-removal hook or automatic pruning is appropriate.

`test_translated_validation_and_action_errors` resolves HA exception translations
in English and Italian, checks placeholders and error metadata, preserves original
validation/transport causes and prevents writes on invalid/busy requests.
`test_fixed_controller_entry_removal` covers online/offline removal, recovery,
registry cleanup and polling shutdown. Existing command/error/entity tests retain
serialization, cancellation, unload and fresh-session recovery coverage.

No hardware commands are run. No official tier is claimed: branding, dependency
provenance, whole-client coverage, verified discovery/reconfiguration and strict
typing remain independent TODOs. Historical validation counts above describe
previous changes, not this PR.

SBR-102 validation: Python 3.14.10; 104 integration tests pass on each existing
matrix target, HA 2026.10.4/plugin 0.13.375 and HA 2026.8.0/plugin 0.13.354.
All 14 adapter modules have 100% line/branch coverage on both targets and satisfy
the unchanged >95% per-module gate. The older target emits 56 mocked-Bluetooth
pytest-socket warnings without failures. All 34 standalone simulated client tests,
Ruff 0.14.3, distribution metadata check, compileall and git diff --check pass.
The integration-only run still reports 54% overall including the embedded client;
this does not close SBR-99. Official hassfest/HACS remain enabled in unchanged CI;
local checks here do not claim their remote results or hardware evidence.

### SBR-101 merge validation (2026-11-08)

Merged main `9ef98a6` (SBR-102), preserving its translated errors and lifecycle
exemptions alongside the SBR-101 reconfiguration evidence and discovery TODOs.
The combined branch passes 123 integration tests on each existing HA target
(2026.8.0/plugin 0.13.354 and 2026.10.4/plugin 0.13.375), with 100% line/branch
coverage in every one of the 14 adapter modules and the >95% gate passing on
both. The older target reports 75 mocked-Bluetooth pytest-socket warnings.
All 34 client tests, Ruff 0.14.3, distribution validation, compileall, diff checks
and full official hassfest (Core `357cae5`: 1 integration, 0 invalid) pass.
Discovery still requires supervised WB-4 advertisement evidence; no hardware
commands were run and no tier is claimed. Remote CI results are not asserted.

## SBR-106 RSSI and polling freshness

Reviewed official Quality Scale rules for entity availability, device classes,
categories, translations, polling and lifecycle. Two enabled diagnostic sensors
share the existing coordinator: RSSI uses HA's cached connectable advertisement
(signal_strength/dBm/measurement), and Last fetched uses an aware UTC timestamp
set only after a successful full poll. RSSI is unknown without advertisement data.
Last fetched remains available during outages so stale data can be identified;
commands preserve both poll metadata fields. No new scan, connection or timer.

`test_entities.py` covers actual HA values, en/it names, categories, enabled
registry defaults, shared device identity, unknown RSSI, failed-poll timestamp
retention, recovery and unload. Existing lifecycle tests include both sensors;
`test_commands.py` checks commands do not advance polling metadata. README
explains advertisement caching and timestamp semantics. Applicable checklist
entries are updated. Existing hardware, discovery, provenance, whole-client
coverage and other TODOs remain; no Quality Scale tier is claimed.

References: https://contributors.home-assistant.io/core/quality-scale/ and
https://contributors.home-assistant.io/core/integrations/bluetooth/.

SBR-106 validation: Python 3.14.10; all 126 integration tests pass on both
HA 2026.10.4/plugin 0.13.375 and HA 2026.8.0/plugin 0.13.354. All 14 adapter
modules have 100% line/branch coverage and pass the >95% per-module gate.
All 34 client tests, Ruff, distribution checks, compileall and git diff --check
pass. HA 2026.8.0 emits 78 mocked-Bluetooth pytest-socket warnings. No hardware
validation was performed; these results do not establish whole-client coverage.
