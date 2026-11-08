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
This repository uses the manually dispatched **Prepare release** workflow instead
of release-please automation. Merging a PR never publishes a release.

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

- [ ] Confirm GitHub detects the MIT LICENSE approved for this repository and
      review dependency/protocol provenance before distribution.
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

## Versioning policy

Use stable Semantic Versioning: MAJOR.MINOR.PATCH, with no leading zeroes.
Increment PATCH for compatible fixes, MINOR for compatible features, and MAJOR
for incompatible changes. During 0.x development, MINOR may contain breaking
changes; explain migration steps at the top of the release notes. Never reuse
or move a published tag. The manifest contains `0.1.0`; its tag is `v0.1.0`.
Prerelease suffixes are not supported by this workflow.

## Authorized release procedure

1. Complete the pre-publication checklist. In a reviewed release PR, update the
   manifest version (the initial candidate is already 0.1.0) and document changes,
   compatibility, migration steps and unresolved limits. Merge after CI passes.
2. Copy the full 40-character reviewed commit SHA from main. In GitHub Actions,
   run **Prepare release** from **main**, providing that SHA. CLI equivalent:
   `gh workflow run release.yml --ref main -f commit=<reviewed-sha>`.
   The workflow checks main ancestry, requires the latest main push runs of both
   **Lint and tests** and **HACS validation** to have succeeded for that exact SHA,
   validates the source distribution and version, and rejects existing tags or
   releases. It creates a **draft** named `v<manifest version>` with generated notes
   targeting that SHA. There is no wheel, PyPI upload or ZIP asset.
3. Review the draft target and generated notes. Edit the notes to put migration
   steps, compatibility and known limitations first. Obtain first-release
   authorization after the source-install report is accepted, then publish the
   draft through GitHub Releases. GitHub creates the version tag at the selected
   SHA when the draft is published. HACS discovers the published release and
   downloads its tagged source tree. Complete the fresh HACS install check above.
4. A failed CI check must be fixed and rerun for the same candidate, or a new
   reviewed SHA selected. If draft creation succeeded but the workflow was
   interrupted, review the existing draft rather than rerunning it. Delete an
   unpublished incorrect draft before preparing again; never move a published tag.
5. For rollback, reinstall a previously validated HACS version and restart HA.
   For the first release, remove the integration if no known-good version exists;
   preserve HA backups and report failures. Withdraw a faulty release if needed,
   then ship a fix with a higher version. Do not replay timed-out commands.

No release workflow runs on merge or tag push. The workflow uses the repository
GitHub token with contents-write and actions-read permissions; no PAT is needed.
Repository branch protection should require every CI job; setting that policy
remains a maintainer action outside source configuration.

Reference: [HACS release guidance](https://contributors.home-assistant.io/marketplace/guides/releases/).

## Repository metadata required by HACS

HACS also checks GitHub repository settings, which cannot be supplied through
`hacs.json`. Before merging the distribution PR, a maintainer with repository
administration permission must set a non-empty description and topics. For this
repository the intended values can be applied with:

```bash
gh repo edit petretiandrea/hass-solem-irrigation \
  --description 'Home Assistant custom integration and embedded local BLE client for SOLEM WooBee V2 / WB-4 irrigation controllers' \
  --add-topic home-assistant --add-topic hacs --add-topic custom-integration \
  --add-topic bluetooth --add-topic irrigation --add-topic solem-woobee
```

The repository includes the MIT `LICENSE`, selected with the owner's authorization,
consistent with hass-sorgenia. Confirm GitHub recognizes it after merge.
Do not add license, description or topics to HACS `ignore` to obtain a green job.
After applying settings and merging the approved license, rerun HACS on the
candidate branch and inspect the result. No tag or release is required.

## SBR-100 current evidence

The [provenance audit](dependency-provenance.md) supersedes the historical
SBR-96 missing metadata/access findings: main HACS now passes and GitHub detects
MIT, description and topics. Local brand assets are prepared for HA 2026.3+;
keep the brands ignore pending candidate/installed validation. Resolve the
recorded MySOLEM derivation evidence before the first release. This audit does
not authorize a release or change the embedded/no-PyPI distribution decision.
