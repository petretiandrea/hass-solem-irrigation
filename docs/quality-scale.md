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

Remaining Gold work (verified discovery, exception translations and lifecycle
configuration flows) remains visible in the checklist. SBR-103 implements the
custom-repository strict typing gate; Core registration remains an upstreaming step.
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


## SBR-103 strict typing (custom repository)

Reviewed the [strict-typing rule](https://contributors.home-assistant.io/core/quality-scale/strict-typing/)
on 2026-11-07 against main `f1902d3`. This independent change implements the
custom repository's typing gate; it does not assert a cumulative or official tier.
All other checklist TODOs remain open.

`pyproject.toml` enables mypy strict mode on Python 3.14 for the entire
`custom_components/solem_woobee` directory: 22 modules, including all eight
embedded-client modules. No excluded modules, blanket ignores, missing-import
suppression, explicit `Any`, or unchecked decorator casts are used. The pinned
`requirements_typing.txt` selects mypy 1.19.1, HA 2026.8.0 (the minimum supported
HA API), Bleak/cryptography with their inline types, and requests/PyYAML stubs.
This typing environment is separate from the preserved HA regression matrix
(2026.8.0/plugin 0.13.354 and 2026.10.4/plugin 0.13.375).

Entry setup/unload, coordinator, platforms and diagnostics use
`WooBeeConfigEntry = ConfigEntry[WooBeeCoordinator]`; the user flow returns
`ConfigFlowResult`. Persisted address/options and backup JSON are checked before
entering typed domain APIs. Dynamic binary-sensor attribute access is replaced
by explicit boolean fields. BLE inspection and session factory protocols, async
context managers, transaction ownership and the serialization decorator preserve
concrete argument/return types. Existing BLE 0.x/2.x inspection compatibility,
unknown values and command safety boundaries remain covered by simulated tests.

The distributed `woobee_api` package now contains `py.typed`. CI's new `typing`
job runs strict mypy, builds wheel and sdist using pinned tooling, and runs
`scripts/check_typed_distribution.py` to inspect both artifacts for the marker
and every client module. HACS still installs the embedded source tree; no PyPI
publication or release is introduced.

Reproduce locally with Python 3.14:

```bash
python -m pip install -e . -r requirements_typing.txt
python -m mypy
python -m build --no-isolation
python scripts/check_typed_distribution.py
```

For a future **Home Assistant Core contribution**, separately add
`homeassistant.components.solem_woobee.*` alphabetically to Core's `.strict-typing`
file, regenerate Core's mypy configuration with
`python -m script.hassfest -p mypy_config`, and run Core's checks. Creating a
similarly named file here would not register this custom integration in Core.
The checklist's `done` records this repository's implementation only.

Reconfirmed `async-dependency`: `BLETransport`, `SolemSession` and
`WooBeeConnection` await BLE connect/authentication/notification/read/write and
cleanup operations; timeouts bound I/O and `tests/test_session.py` exercises
ownership, cancellation, serialization and no automatic replay. Reconfirmed
`inject-websession` exemption: the HA adapter supplies an address-bound
`BleakClient` using HA Bluetooth discovery; there is no HTTP dependency or
websession to inject. These findings do not establish physical-device behavior.

SBR-103 local validation: Python 3.14.10; strict mypy reports no issues in all
22 modules. Both HA targets pass 105 integration tests; every one of the 14
adapter modules has 100% line/branch coverage and passes the existing >95%
per-module gate. HA 2026.8.0 retains the 54 pre-existing mocked-Bluetooth socket
warnings. All 37 standalone client tests pass, including malformed backup and
session-boundary tests. Ruff 0.14.3, compileall, source distribution checks,
wheel/sdist marker/module verification and git diff --check pass. The whole-client
coverage gap remains explicitly outside this issue; the integration-only overall
coverage measurement is not a whole-integration coverage claim. No hardware,
fresh-install, HACS-download or official tier validation is asserted.
