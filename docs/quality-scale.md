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

Gold/Platinum work (diagnostics, verified discovery, exception translations,
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

Button platform selected because start is timed and stop affects the whole
controller; no invented per-zone stop or retained switch state. See
`docs/manual-irrigation.md` for protocol mappings, duration units/wire limits,
examples, error semantics, external-client races and supervised hardware steps.
The Sorgenia template's platform separation, shared coordinator, stable entity
identity and translations are retained.

Affected rules: action-setup/docs-actions (entity action registered during integration setup with schema and services.yaml), action-exceptions (validation errors,
transport/auth/timeout/invalid-response failures and unconfirmed state),
parallel-updates (one coordinator lock across polling/commands), and entity
lifecycle/identity/device/name/translations/icons/availability. Evidence:
`tests/integration/test_commands.py` plus the existing platform/lifecycle tests.
No optimistic success or automatic command retries; post-command reads publish
actual reported state. An ambiguous command failure requires state verification
before a user retries. No confirmed API rejection code or settling interval is
invented. Exception translations remain TODO for Gold.

The adapter coverage gate includes button.py automatically. Hardware procedure
is documented but has not been executed; firmware latency, physical valve
behavior, maximum practical duration and battery impact remain unverified.
Existing branding, client provenance, whole-client coverage, diagnostics and
strict typing TODOs remain. No Quality Scale tier is claimed.

Validation for SBR-94: Python 3.14.10; 34 client unittests; 67 integration tests
on each of HA 2026.8.0 / pytest plugin 0.13.354 and HA 2026.10.4 / plugin
0.13.375. Per-module line/branch coverage is 100% for all 12 adapter modules;
`check_ha_coverage.py`, compileall and git diff whitespace checks pass. The
minimum-version suite emits pytest-socket warnings from HA Bluetooth setup;
all tests pass without hardware/network access. CI pins compatible test plugins
per HA version and runs the official hassfest action. Whole-client coverage and
the remaining tier TODOs above are not implied by these adapter results.

### CI correction: service target selector

The initial numeric `supported_features: [1]` in services.yaml was not a valid
HA target selector: metadata accepts named standard features, and button has no
standard feature for this integration-specific start capability. Removed that UI
filter; the registered entity action retains its runtime `required_features=[1]`
guard, so targeting the controller stop button cannot start irrigation.
`test_action_description_schema_and_stop_target` validates the YAML with HA's
TargetSelector/field selector schemas and verifies stop-target rejection without
opening a BLE session.

Reproduced the original SERVICES schema error with the official hassfest source
(Core f8cdb14), then ran the full validator successfully after the correction
(1 integration, 0 invalid). Both supported HA versions pass 68 integration tests
with the >95% per-module coverage gate (100% for all 12 adapter modules).
Remote Actions/check visibility remains blocked by the GitHub App's 403 response;
local hassfest success does not assert a remote CI result. Hardware and existing
Quality Scale TODOs remain unchanged; no tier is claimed.
