# HACS distribution and release checklist

## One version, one distribution

`custom_components/solem_woobee/manifest.json` is the only version source.
Hatch reads that value for local development installs; there is no independent
client release and no PyPI upload. The embedded `woobee_api` directory is shipped
with every integration version. HACS installs the component from a GitHub release
tag's source tree, not a wheel or a release ZIP (`zip_release` is not enabled).
The supported baseline is HA 2026.8.0 / Python 3.14 and HACS 2.0.5.

SBR-96 prepares distribution only. **Do not tag or publish the first release as
part of this task.** The current 0.1.0 manifest value is preparation, not proof
that a tested release exists. Until publication, use a reviewed source checkout
for manual installation; HACS release installation must be verified later.

The directly inspected hass-sorgenia template provides the embedded API layout,
HA/HACS minimum metadata, separate hassfest/HACS validation and a manifest version.
This repository deliberately uses a manual release process instead of its
release-please automation so merging a PR cannot publish the first release.

## Required checks for a candidate

Run on Python 3.14 from a clean checkout:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e . ruff==0.14.3
python -m ruff check custom_components scripts tests
python scripts/check_distribution.py
python -m unittest discover -s tests -v
python -m pip install -r requirements_test.txt 'homeassistant==2026.8.0' 'pytest-homeassistant-custom-component==0.13.354'
python -m pytest tests/integration -q --cov=custom_components.solem_woobee --cov-branch --cov-report=term-missing --cov-report=json
python scripts/check_ha_coverage.py
python -m compileall -q custom_components scripts tests
```

Repeat integration tests and coverage in a separate environment with HA
2026.10.4 / plugin 0.13.375. Client tests must also pass without HA installed.
CI runs those checks plus official hassfest and HACS validation. Ruff currently
checks fatal syntax, invalid control flow and undefined names, not formatting or
strict typing. The distribution check validates metadata, JSON, layout and AST
imports, including type-only imports. HACS ignores only brands while the brand
submission is TODO; record that exception when reviewing a candidate.

## Clean-install validation — pending before first release

Record the candidate SHA, version, date, tester, HA/Python/HACS versions, Bluetooth
adapter/proxy, model/type/firmware and results in a release PR. All boxes below
are pending; simulated tests cannot satisfy the physical checks.

- [ ] Resolve licensing/provenance before distribution: this checkout has no
      LICENSE file and GitHub reports no detected license. The maintainer must
      select/confirm licensing; this task does not invent a grant of rights.
- [ ] All candidate CI jobs pass, including hassfest and HACS; review Quality
      Scale TODOs without claiming a tier. Confirm no independent client version.
- [ ] Fresh HA 2026.8.0 profile with working Bluetooth and no previous component,
      config entries or registry entities. Repeat on the newer CI target.
- [ ] Copy only `custom_components/solem_woobee/` from candidate source into the
      configuration directory. Confirm the embedded client is present; restart.
- [ ] Add SOLEM WooBee through Devices & services. Validate WB-4/type 180/firmware
      7.0.2 identity, selection, duplicate prevention and setup failure/recovery.
- [ ] Verify all expected entities, English/Italian names, device associations,
      disabled raw battery, unknown duration versus zero and five-minute updates.
- [ ] Complete supervised commands, offline/recovery and diagnostics checks in
      [diagnostics and validation](diagnostics-and-validation.md) and
      [manual irrigation](manual-irrigation.md). Never actuate unattended hardware.
- [ ] Verify reload, restart, removal/reinstall and preserved entity identities;
      no stuck BLE connection or polling after unload. Review logs for secrets
      before sharing: original client exception chains are not anonymized.
- [ ] With release authorization, create a **draft** for the reviewed version.
      Publish only after the source-install report is accepted. On a fresh HA
      profile add this repository as HACS category Integration and install the
      published tag. Confirm complete client tree, setup and uninstall. Record
      this post-publication distribution check; first-release HACS testing cannot
      be claimed in advance. If it fails, withdraw the release and investigate.

## Authorized release procedure (future, manual)

1. Complete the pre-publication checklist. In a reviewed release PR, change only
   the manifest version using SemVer and add release notes describing changes,
   compatibility and unresolved limits. Merge after all CI gates pass.
2. From a clean main checkout, verify the exact reviewed SHA and version, then
   create a GitHub **draft** release with tag `v<manifest version>` targeting that
   SHA. No additional version file, wheel, PyPI package or ZIP asset is needed.
   Example for a future explicitly approved 0.1.0 candidate:
   `gh release create v0.1.0 --target <reviewed-sha> --draft --title v0.1.0 --notes-file <reviewed-notes.md>`.
3. Review the draft target/tag and notes, obtain first-release authorization,
   then publish the draft through GitHub Releases. HACS uses that tag's manifest
   and source tree. Complete and record the fresh HACS install check above.
4. For rollback, reinstall a previously validated HACS version and restart HA.
   For the first release, remove the integration if no known-good version exists;
   preserve HA backups and report failures. Do not replay timed-out commands.

No release workflow runs on merge or tag push. Credentials for PyPI are neither
required nor used. Repository branch protection should require every CI job;
setting that policy remains a maintainer action outside source configuration.
