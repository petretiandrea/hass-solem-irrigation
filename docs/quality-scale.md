# Quality checks

The [rule checklist](../custom_components/solem_woobee/quality_scale.yaml) records
implementation evidence, exemptions and TODOs. It is a project review tool;
this custom integration has no official Home Assistant Quality Scale tier.

## Run checks

Use Python 3.14. CI configuration in
[client.yml](../.github/workflows/client.yml) defines the supported matrix:
HA 2026.8.0 / pytest plugin 0.13.354 and HA 2026.10.4 / plugin 0.13.375.
Run each pair in a separate environment.

```bash
python -m pip install -e . -r requirements_test.txt ruff==0.14.3 \
  'homeassistant==2026.8.0' 'pytest-homeassistant-custom-component==0.13.354'
python -m ruff check custom_components scripts tests
python scripts/check_distribution.py
python -m coverage run --branch --source=custom_components/solem_woobee -m unittest discover -s tests -v
python -m pytest tests/integration -q --cov=custom_components.solem_woobee --cov-branch --cov-append --cov-report=term-missing --cov-report=json
python scripts/check_ha_coverage.py
python -m compileall -q custom_components scripts tests
```

Start coverage with the standalone suite, then append HA execution. The gate
requires greater than 95% lines and branches separately for every shipped
Python module, including the embedded client, and 100% for both config-flow
modules. Missing modules, absent branch measurements and exactly 95% fail.
Modules without executable branches use a 0/0 branch denominator.
`tests/test_coverage_gate.py` verifies these conditions.

In a separate environment, install `-e . -r requirements_typing.txt`, then run:

```bash
python -m mypy
python -m build --no-isolation
python scripts/check_typed_distribution.py
```

Strict mypy covers the adapter and client. Typed config entries, validated
mapping boundaries and the client's `BLETransport` protocol separate HA from
BLE. Built wheel/sdist checks verify shipped modules and `py.typed`. A future
Core contribution also needs registration in Core's `.strict-typing` file and
regenerated mypy configuration.

Client tests also run without HA installed. CI includes official hassfest and
HACS validation. HACS currently ignores brands pending installed validation.
Ruff checks fatal syntax, control-flow errors and undefined names; formatting
is not gated.

## Test evidence

| Behavior | Tests |
| --- | --- |
| Setup validation, duplicates, failures and retry | `tests/integration/test_config_flow.py`, `test_init.py` |
| Shared polling, listener lifecycle, unknown versus zero, failure/recovery | `tests/integration/test_coordinator.py`, `test_entities.py` |
| HA states, translations, metadata, registry associations and unload | `tests/integration/test_entities.py` |
| Timed valve actions, defaults, guarded close, serialization and no retries | `tests/integration/test_commands.py` |
| Translated exceptions, original causes, outage logging and entry removal | `tests/integration/test_errors.py` |
| Address changes, serial validation, collisions and frozen entity identity | `tests/integration/test_reconfigure.py` |
| Cached diagnostics allowlist and no BLE I/O | `tests/integration/test_diagnostics.py` |
| Mapping validation and typed boundaries | `tests/integration/test_typing_boundaries.py` |
| Frame parsing, schedules, backup validation and fake BLE exchange | `tests/test_client.py`, `test_coverage_paths.py`, `test_session.py` |
| CLI inspection and menu behavior | `tests/test_inspect_script.py`, `test_menu.py` |

The latest recorded combined validation (2026-11-08, SBR-103 merge) passed
58 standalone tests and 134 HA tests on each matrix target. All 22 shipped
modules measured 100% lines and branches; strict mypy, Ruff, distribution and
typed-package checks passed. The older HA target emitted 78 mocked-Bluetooth
socket warnings. These are historical results, not a substitute for candidate CI.

Tests use simulated BLE and synthetic identifiers. They do not establish
physical valve behavior, battery life or proxy compatibility.

## Remaining work

| Area | Required evidence |
| --- | --- |
| Branding | Installed icons/logo and candidate HACS checks; see [provenance](dependency-provenance.md) |
| Dependency transparency | MySOLEM acquisition/derivation record and embedded-client release provenance |
| Discovery and address updates | Verified WB-4 advertisements and stable advertised identity; see [discovery](bluetooth-discovery.md) |
| Hardware and distribution | Supervised valve, recovery, battery/proxy and clean-install checks; see [release checklist](releasing.md) |

Existing exemptions cover the supported feature set: no custom triggers or
conditions, user credentials, HTTP client, dynamic child devices or verified
actionable repair condition. Each entry contains its reason in the YAML
checklist. Valve fault bits have no verified software remedy, and raw battery
has no known low-battery threshold. A BLE outage is not evidence that a device
was removed; deleting the config entry removes its fixed controller and zones.

## Documentation review

The README covers installation, prerequisites, configuration, supported devices
and functions, polling, limitations, examples, troubleshooting and removal.
The action guide covers defaults, duration bounds and command errors. The
SBR-108 edit consolidates those topics and removes obsolete PR reports while
retaining the checklist's TODOs and test evidence. Applicable documentation
rules retain their status; this edit changes no integration behavior.

The release workflow creates drafts before checking for pending stable versioned
drafts. It prepares the next release PR only when none remain, preserving manual
publication and avoiding history replay before GitHub creates the tag. See the
[release procedure](releasing.md#publish-and-recover). This CI change leaves HA
adapter tests, coverage and rule statuses unchanged.

References: [Quality Scale](https://contributors.home-assistant.io/core/quality-scale/),
[installation instructions](https://contributors.home-assistant.io/core/quality-scale/docs-installation-instructions/),
[known limitations](https://contributors.home-assistant.io/core/quality-scale/docs-known-limitations/).
