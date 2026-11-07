# SBR-104 revision acceptance report

Date: 2026-11-07 UTC. Reviewer: Overlord agent. Candidate: `f1902d36aee6dfa59233c1d4572b35d8d720e038`, confirmed against remote main at execution start. Manifest: 0.1.0. Report changes are documentation only; this report does not certify subsequent sibling changes or confer a tier.

## Execution and access

| Check | Result and evidence |
| --- | --- |
| Exact revision | Clean checkout and `git ls-remote origin refs/heads/main` both identify the SHA above |
| Python / installed HA / HACS | Not installed or available in this workspace; no live HA profile or Bluetooth hardware supplied |
| Requested project environment | Runtime create/attach returned “attached” to the same workspace; Python remains unavailable |
| Current automated tests, Ruff, distribution check, coverage, compileall | Not executed: Python unavailable. No new passing test or coverage result claimed |
| Current remote CI | Unknown: `gh run list --limit 6 --json databaseId,headSha,status,conclusion,url,name` exited 4 requesting authentication; git remote access does not establish Actions access |
| Historical automated evidence | docs/quality-scale.md records 99 integration tests per HA target, 34 client tests and 100% across 14 adapter modules, plus local hassfest. These are previous reports, not reruns or authenticated current CI evidence |
| Supported test targets | Python 3.14; HA 2026.8.0 / plugin 0.13.354 and HA 2026.10.4 / plugin 0.13.375, per checked-in CI. Actual installed versions: unavailable |
| Source review | Checklist, release/diagnostic procedures, manifest, workflows and adapter coverage script reviewed |
| Fresh source install / HACS / UI | Not executed: no running HA, Bluetooth installation or published release validated here |

The software report is delivered with execution blockers explicit. It is not a passing release acceptance. Reproduce automated checks using [releasing.md](releasing.md); collect new results against this exact SHA, preserving command exits and environment versions. Do not transplant future results onto this baseline.

## Installation-facing checks

| Area | Existing simulated evidence in tests/integration | Current installation result |
| --- | --- | --- |
| Configuration, duplicate prevention, errors | test_config_flow.py | Not executed |
| Registry/device identity and stable IDs | test_entities.py | Not executed |
| English/Italian names, metadata, disabled battery | test_entities.py, test_commands.py | Not executed |
| Cached diagnostics / sensitive-field exclusion / HTTP download | test_diagnostics.py | Not executed |
| Reload/unload, connection closure, polling teardown | test_init.py, test_entities.py, test_coordinator.py | Not executed |
| Offline recovery / exception causes | test_errors.py, test_coordinator.py | Not executed |

These files are evidence locations, not a claim they ran in this session.

## Rule-by-rule matrix

Statuses below are the existing project checklist decisions at the candidate SHA. “done” means recorded source/test/document evidence, not independently rerun acceptance. Every row was reviewed against the checklist comment; execution limitations above apply to all rows. Official reference: [Quality Scale](https://contributors.home-assistant.io/core/quality-scale/). The [coverage rule](https://contributors.home-assistant.io/core/quality-scale/test-coverage/) cannot be established by the adapter-only gate.

| Rule | Recorded status | Candidate evidence / remaining gap | Follow-up |
| --- | --- | --- | --- |
| action-setup | done | Entity action registered during async_setup with schema and services.yaml; test_commands.py verifies routing. | — |
| docs-actions | done | docs/manual-irrigation.md documents valve actions, saved defaults, conditional close and global stop, examples and errors. | — |
| docs-conditions | exempt | No custom trigger or condition platforms are exposed. Manual command action documented separately. | — |
| docs-triggers | exempt | No custom trigger or condition platforms are exposed. Manual command action documented separately. | — |
| appropriate-polling | done | Five-minute conservative BLE interval; only real subscribers activate polling. See docs/coordinator.md; battery impact remains unmeasured. | — |
| brands | todo | Verify or submit WooBee branding in the Home Assistant brands repository. | [SBR-100](https://linear.app/sbriccohouse/issue/SBR-100) |
| common-modules | done | const.py, data.py and coordinator.py separate constants, entry runtime types and shared refresh ownership. | — |
| runtime-data | done | const.py, data.py and coordinator.py separate constants, entry runtime types and shared refresh ownership. | — |
| config-flow | done | Bluetooth selection validates identity/state before creating an entry; normalized address prevents duplicates. tests/integration/test_config_flow.py. | — |
| test-before-configure | done | Bluetooth selection validates identity/state before creating an entry; normalized address prevents duplicates. tests/integration/test_config_flow.py. | — |
| unique-config-entry | done | Bluetooth selection validates identity/state before creating an entry; normalized address prevents duplicates. tests/integration/test_config_flow.py. | — |
| config-flow-test-coverage | done | Flow modules have 100% line/branch coverage in integration tests. | — |
| dependency-transparency | todo | Embedded woobee_api is the agreed custom-integration architecture. A Core submission requires reviewing library packaging, license and public release provenance; no exemption claimed. | [SBR-100](https://linear.app/sbriccohouse/issue/SBR-100) |
| docs-high-level-description | done | README.md documents verified WB-4 scope, HACS/manual installation, configuration and removal; docs/releasing.md records pending clean-install acceptance. | — |
| docs-installation-instructions | done | README.md describes WB-4 BLE scope, manual installation/configuration and removal. | — |
| docs-removal-instructions | done | README.md describes WB-4 BLE scope, manual installation/configuration and removal. | — |
| entity-event-setup | done | CoordinatorEntity owns subscription lifecycle; no synthetic listener. Lifecycle regression test covers add/remove and unload. | — |
| entity-unique-id | done | Read platforms use normalized controller/zone IDs plus a field suffix. Actual registry IDs survive metadata changes and reload; tests/integration/test_entities.py. | — |
| has-entity-name | done | All read entities inherit has_entity_name and use translated names with zone placeholders; actual HA names tested in English and Italian, including zone valves and global stop button. | — |
| test-before-setup | done | async_config_entry_first_refresh completes before registry and platform setup; failures retry setup. | — |
| action-exceptions | done | Command validation, transport failures and unconfirmed outcomes raise HA errors; test_commands.py. test_errors.py verifies original exception causes, messages, notes and nested chains. | — |
| parallel-updates | done | All platforms set PARALLEL_UPDATES=0; coordinator lock serializes commands and reads. test_commands.py. | — |
| config-entry-unloading | done | Setup/unload/reload, timer shutdown and failed platform unload tested in tests/integration. | — |
| docs-configuration-parameters | done | README.md documents BLE address selection, HA/Python prerequisites and Bluetooth reachability; no user credentials required. Per-zone local duration defaults documented in docs/manual-irrigation.md. | — |
| docs-installation-parameters | done | README.md documents BLE address selection, HA/Python prerequisites and Bluetooth reachability; no user credentials required. Per-zone local duration defaults documented in docs/manual-irrigation.md. | — |
| entity-unavailable | done | Real HA state tests cover unknown partial durations, reported zero, unavailable state on read failure and recovery. Connectivity remains available to report the last read outcome. | — |
| integration-owner | done | manifest.json codeowners names petretiandrea. | — |
| log-when-unavailable | done | Coordinator logs first failure and recovery without per-poll duplication; test_failure_and_recovery_logged_once verifies two consecutive failures and two successful reads. test_errors.py checks availability messages at DEBUG, original causal chains and fresh-session recovery. | — |
| reauthentication-flow | exempt | 'No user account or renewable credential: fixed protocol key and fresh challenge on every BLE connection. Rejection is retried with a new session.' | — |
| test-coverage | todo | HA wrapper modules including valve and read platforms gated above 95% per module. Embedded client modules need complete coverage assessment; wrapper results alone do not meet the whole-integration rule. | [SBR-99](https://linear.app/sbriccohouse/issue/SBR-99) |
| devices | done | All 23 registry entities share the normalized controller device; registry associations remain stable across metadata changes and reload. | — |
| diagnostics | done | diagnostics.py exports only allowlisted cached operational fields; no identity, config, raw frames or session secrets. test_diagnostics.py verifies empty, stale and partial data without I/O. | — |
| discovery | todo | A verified Bluetooth advertisement matcher is not implemented. | [SBR-101](https://linear.app/sbriccohouse/issue/SBR-101) |
| discovery-update-info | todo | A verified Bluetooth advertisement matcher is not implemented. | [SBR-101](https://linear.app/sbriccohouse/issue/SBR-101) |
| docs-data-update | done | README.md and docs/coordinator.md describe WB-4 firmware scope, read snapshots, missing values, polling and hardware-validation limits. | — |
| docs-known-limitations | done | README.md and docs/coordinator.md describe WB-4 firmware scope, read snapshots, missing values, polling and hardware-validation limits. | — |
| docs-supported-devices | done | README.md and docs/coordinator.md describe WB-4 firmware scope, read snapshots, missing values, polling and hardware-validation limits. | — |
| docs-supported-functions | done | README.md and docs/coordinator.md describe WB-4 firmware scope, read snapshots, missing values, polling and hardware-validation limits. | — |
| docs-examples | done | README provides dashboard entity-picker and valve-fault automation examples without assuming entity IDs. | — |
| docs-troubleshooting | done | README covers failed reads, BLE range/connection slots, next poll/reload, optional unknown pages and enabling diagnostic entities. docs/diagnostics-and-validation.md documents anonymous downloads and supervised hardware checks. | — |
| docs-use-cases | done | README explains irrigation monitoring and per-zone valve-fault notifications, with reported-state versus water-flow limitations. | — |
| dynamic-devices | exempt | One fixed four-zone WB-4 per config entry; no dynamically added child hardware. | — |
| entity-category | done | Connectivity, clock/input flags, valve faults and raw battery are diagnostic. Operational status remains uncategorized; zone valves and global stop are operational; duration defaults are local HA options. | — |
| entity-device-class | done | Water valves, duration in seconds, running activity, problem flags and read connectivity tested. Unscaled battery has no fabricated class, unit or statistics. | — |
| entity-disabled-by-default | done | Unscaled raw battery is diagnostic and disabled by default; tests verify registry default and explicit enable/reload. Other exposed fields are operationally useful. | — |
| entity-translations | done | strings.json and en/it translations cover read entities and zone valves and global stop button and zone placeholders; actual HA names verified in both languages. | — |
| icon-translations | done | icons.json supplies icons by translation key for enabled/manual/input flags and raw battery. Duration, running, problem and connectivity retain HA device-class icons; no Python icon overrides. | — |
| exception-translations | todo | Review translated failures, address reconfiguration and applicable repair/device cleanup flows before claiming Gold. | [SBR-102](https://linear.app/sbriccohouse/issue/SBR-102) |
| reconfiguration-flow | todo | Review translated failures, address reconfiguration and applicable repair/device cleanup flows before claiming Gold. | [SBR-101](https://linear.app/sbriccohouse/issue/SBR-101) |
| repair-issues | todo | Review translated failures, address reconfiguration and applicable repair/device cleanup flows before claiming Gold. | [SBR-102](https://linear.app/sbriccohouse/issue/SBR-102) |
| stale-devices | todo | Review translated failures, address reconfiguration and applicable repair/device cleanup flows before claiming Gold. | [SBR-102](https://linear.app/sbriccohouse/issue/SBR-102) |
| async-dependency | done | Embedded client uses asynchronous BLE transport, bounded operations and session cleanup; client unit tests cover ownership and cancellation. | — |
| inject-websession | exempt | Local BLE integration; no HTTP client or web session. | — |
| strict-typing | todo | Complete strict type checking for wrapper and embedded client; no strict typing gate currently runs. | [SBR-103](https://linear.app/sbriccohouse/issue/SBR-103) |

## Physical acceptance — pending

No hardware accessed, no controller writes issued and no operator observations supplied. AGENTS.md records earlier WB-4/type 180/firmware 7.0.2 protocol evidence; this is not verification of this HA revision. Device/firmware for this execution, physical zone behavior, offline recovery, latency, polling freshness and battery impact are all unverified. No hardware pass or cumulative tier is claimed.

An operator may supply read-only observations using the template in [diagnostics-and-validation.md](diagnostics-and-validation.md). Any physical write additionally needs explicit command authorization and supervised hardware access. SBR-99–SBR-103 own their own regression evidence; none must merge to deliver this revision-bound report.
