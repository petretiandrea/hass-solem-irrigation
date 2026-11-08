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
Release Please prepares version/changelog PRs and draft GitHub releases.
Publishing a reviewed draft remains a manual maintainer action.

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

Release Please reads Conventional Commits and maintains a release PR containing
`CHANGELOG.md`, the integration manifest and `.release-please-manifest.json`.
The last file is automation bookkeeping, not a second runtime/package version;
Hatch continues reading only the integration manifest. Its initial `0.0.0` value
means no release exists yet. The Python strategy starts the first release at
0.1.0, matching the prepared integration version. It preserves the dynamic
version in `pyproject.toml`; no standalone client version is introduced.

Use squash-merge PR titles such as `fix: handle a BLE disconnect` (PATCH),
`feat: expose a new sensor` (MINOR), and `feat!: change an action schema`
(breaking change). Include the issue ID after the prefix, for example
`fix: SBR-123 handle a BLE disconnect`. A `BREAKING CHANGE:` footer also declares
a breaking change. Before 1.0, breaking changes bump MINOR; after 1.0, MAJOR.
Documentation, test and CI maintenance alone do not normally trigger a release.
Historical issue-prefixed commits may be omitted from generated notes; review
and supplement the initial changelog. Never reuse or move a published tag.
Stable versions use MAJOR.MINOR.PATCH and tags use `vMAJOR.MINOR.PATCH`.

## Repository setup

The workflow uses the automatically supplied GITHUB_TOKEN with Contents,
Pull requests and Issues write permissions. No additional token secret or PAT
is required. Under Settings → Actions → General → Workflow permissions, enable
**Allow GitHub Actions to create and approve pull requests**. Organization policy
may restrict this setting. Branch protection should require candidate checks
and human review; the bot must not bypass it.

When Release Please opens or updates a PR with GITHUB_TOKEN, its pull_request
CI runs require approval. A maintainer with write access must select
**Approve workflows to run** in the PR merge box, then wait for all checks.
Approve again after bot updates if prompted. Bot push/tag/release events do not
trigger other workflows automatically; release validation uses the approved PR
checks and the normal main CI after the maintainer merges the release PR.
See [GitHub workflow triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow).

## Authorized release procedure

1. On pushes to main, **Release Please** opens or updates a release PR from the
   Conventional Commits since the previous release. The workflow can also be
   rerun manually from main. Review the proposed version and changelog; add
   migration instructions, compatibility and unresolved limits. Keep the
   generated release metadata and `autorelease: pending` label intact.
2. Approve the generated PR workflows using **Approve workflows to run**.
   Complete the pre-publication checklist and require all candidate CI checks,
   including HACS, hassfest, typing and both HA test targets, before merging the
   release PR. This setup PR does not publish a release. Do not merge the first
   generated release PR until its source-install acceptance evidence is ready.
3. After the release PR merges, Release Please creates a **draft GitHub release**
   for that merge commit with the matching version tag and changelog notes.
   A draft is not offered as an update by HACS. Wait for main CI on the exact
   candidate SHA to pass; verify tag/target and manifest version, review the notes,
   and obtain first-release authorization before publishing through GitHub
   Releases. Complete and record the fresh HACS install check above.
4. If automation fails, check Actions permissions, PR workflow approval and CI, then rerun
   **Release Please** on main. Inspect existing release PRs/drafts before any
   manual recovery; do not delete lifecycle labels or move published tags.
5. For rollback, reinstall a previously validated HACS version and restart HA.
   If none exists, remove the integration and preserve HA backups. Withdraw a
   faulty release if necessary, then ship a fix with a higher version. Never
   replay timed-out hardware commands.

HACS downloads the tagged component source tree, including `woobee_api/`; no
wheel or ZIP asset is needed. Publication remains a manual step. First-release
clean-install, provenance and supervised hardware acceptance remain pending.

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
