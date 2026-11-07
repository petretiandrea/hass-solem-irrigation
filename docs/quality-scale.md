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

Silver is not claimed: branding and dependency provenance TODOs remain. SBR-99
now measures and gates every shipped module using combined standalone and HA
tests; exact results and reproducible commands are recorded below.
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
python -m coverage run --branch --source=custom_components/solem_woobee -m unittest discover -s tests -v
python -m pytest tests/integration -q --cov=custom_components.solem_woobee --cov-branch --cov-append --cov-report=term-missing --cov-report=json
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

The checklist records these rules individually. The historical adapter-only
measurements do not establish Silver compliance.
SBR-99 replaces that coverage gate; branding, library provenance and remaining
checklist items still prevent a tier claim.

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

## SBR-99 combined shipped-module coverage

Measured on 2026-11-07 using Python 3.14.10, based on current main
`f1902d36aee6dfa59233c1d4572b35d8d720e038` plus this PR. Both matrix
pairs passed: HA 2026.8.0 / pytest plugin 0.13.354 and HA 2026.10.4 /
pytest plugin 0.13.375. Each ran 55 standalone unittest tests and 99 HA
tests.
Coverage versions were 7.15.2 and 7.16.2 respectively; pytest-cov was 7.1.0.
The older HA target emits 54 dependency deprecation warnings; no test failures.

The commands in Validation start a fresh branch measurement with unittest,
then append HA execution into that same measurement before reporting/gating.
CI repeats this independently for each matrix pair. The filesystem source root
includes unexecuted modules; the gate derives its expected inventory recursively
from all shipped integration `.py` files and rejects absent entries. It checks
unrounded line and branch ratios separately (>95% each), plus 100% for both
config-flow modules. No module exclusions or average-based acceptance apply.
Gate tests explicitly reject missing entries, zero execution, absent branch
measurement, exactly 95% in either metric and incomplete config-flow coverage.

All measured modules are listed below, relative to `custom_components/solem_woobee/`.
Every nonzero branch denominator has 100% coverage. `0/0` means no executable
branches (accepted as vacuously complete), including the transport Protocol's
method declarations; this does not simulate or prove a physical BLE backend.

| Module | 2026.8.0 lines | 2026.8.0 branches | 2026.10.4 lines | 2026.10.4 branches |
| --- | --- | --- | --- | --- |
| `__init__.py` | 26/26 (100%) | 2/2 | 26/26 (100%) | 2/2 |
| `binary_sensor.py` | 37/37 (100%) | 4/4 | 37/37 (100%) | 4/4 |
| `button.py` | 17/17 (100%) | 0/0 | 17/17 (100%) | 0/0 |
| `config_flow.py` | 2/2 (100%) | 0/0 | 2/2 (100%) | 0/0 |
| `config_flow_handler/__init__.py` | 30/30 (100%) | 4/4 | 30/30 (100%) | 4/4 |
| `connection.py` | 16/16 (100%) | 2/2 | 16/16 (100%) | 2/2 |
| `const.py` | 1/1 (100%) | 0/0 | 1/1 (100%) | 0/0 |
| `coordinator.py` | 59/59 (100%) | 14/14 | 59/59 (100%) | 14/14 |
| `data.py` | 7/7 (100%) | 0/0 | 7/7 (100%) | 0/0 |
| `diagnostics.py` | 12/12 (100%) | 2/2 | 12/12 (100%) | 2/2 |
| `entity.py` | 24/24 (100%) | 2/2 | 24/24 (100%) | 2/2 |
| `sensor.py` | 30/30 (100%) | 0/0 | 30/30 (100%) | 0/0 |
| `services.py` | 13/13 (100%) | 2/2 | 13/13 (100%) | 2/2 |
| `valve.py` | 39/39 (100%) | 0/0 | 39/39 (100%) | 0/0 |
| `woobee_api/__init__.py` | 9/9 (100%) | 0/0 | 9/9 (100%) | 0/0 |
| `woobee_api/client.py` | 68/68 (100%) | 8/8 | 68/68 (100%) | 8/8 |
| `woobee_api/errors.py` | 5/5 (100%) | 0/0 | 5/5 (100%) | 0/0 |
| `woobee_api/models.py` | 29/29 (100%) | 4/4 | 29/29 (100%) | 4/4 |
| `woobee_api/programs.py` | 186/186 (100%) | 58/58 | 186/186 (100%) | 58/58 |
| `woobee_api/protocol.py` | 318/318 (100%) | 82/82 | 318/318 (100%) | 82/82 |
| `woobee_api/responses.py` | 96/96 (100%) | 32/32 | 96/96 (100%) | 32/32 |
| `woobee_api/transport.py` | 2/2 (100%) | 0/0 | 2/2 (100%) | 0/0 |

New evidence: `tests/test_coverage_paths.py` covers malformed identity/state/
program responses, incomplete zone pages preserving None, backup validation,
schedule boundaries, discovery delegation, inspection read failures, managed
scope reuse, and simulated command/backup/restore frame delegation.
`tests/test_session.py` adds authentication cancellation/idempotence, unknown
acknowledgements, read/write failures, connect timeout, empty/overflow/wrong/
excess response pages, and cleanup errors preserving the primary failure.
These augment the existing simulated BLE suite and retained HA state, action,
registry, availability, polling and unload tests. Ruff, distribution validation
and compileall also passed.

Only the test-coverage gap is closed here. No hardware was accessed or commands
sent to a controller. Automated simulation does not establish hardware behavior,
battery impact, clean-install acceptance or an official quality tier. Other
checklist TODOs remain. No external access/evidence blocker remains for SBR-99's
automated coverage acceptance; physical evidence belongs to the separate review.
