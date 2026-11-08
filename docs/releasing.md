# Releases

The integration manifest is the version source. Hatch reads it for local client
builds; the client has no separate release or PyPI package. HACS downloads the
tagged component source, including `woobee_api/` and brand assets.

## Candidate checks

Run the [quality checks](quality-scale.md) against both HA matrix targets and
require candidate CI, including hassfest, HACS and strict typing. Verify the
manifest version matches the proposed `vMAJOR.MINOR.PATCH` tag. Review the
[provenance gaps](dependency-provenance.md) and Quality Scale TODOs.

Clean-install and supervised hardware acceptance remain pending. Record the
candidate SHA, version, date, tester, HA/Python/HACS versions, adapter/proxy,
controller model/type/firmware and results in the release PR. Keep identifiers
out of public reports.

- [ ] Review source license and protocol/dependency provenance.
- [ ] Install the complete component into a fresh HA 2026.8.0 profile with
      working Bluetooth; repeat on the newer CI target.
- [ ] Configure WB-4/type 180/firmware 7.0.2. Check duplicates and setup recovery.
- [ ] Check entity names in English/Italian, controller associations, disabled
      raw battery, unknown versus zero, and five-minute updates.
- [ ] Complete [manual irrigation](manual-irrigation.md#supervised-device-verification)
      and [diagnostics/recovery](diagnostics-and-validation.md#hardware-validation).
- [ ] Check restart, reload, removal/reinstall, stable identities and no BLE or
      polling resources left after unload. Review INFO/DEBUG logs before sharing.
- [ ] Verify installed icon/logo in light/dark themes and normal/HiDPI resolution.
- [ ] After publication, install the tag through HACS in a fresh profile and check
      the embedded client, setup and uninstall. Record this separately from the
      source-install check; withdraw a faulty release and investigate.

## Versioning

Release Please reads Conventional Commits and updates `CHANGELOG.md`, the
manifest and `.release-please-manifest.json` in a release PR. The latter is bot
bookkeeping. `pyproject.toml` keeps its dynamic version.

Use squash titles such as `fix: SBR-123 handle a BLE disconnect` (patch),
`feat: add a sensor` (minor), or `feat!: change an action schema` (breaking).
A `BREAKING CHANGE:` footer also marks a breaking change. Breaking changes bump
minor before 1.0 and major after 1.0. Documentation/test/CI maintenance normally
does not trigger a release. Review generated notes for omitted historical commits.
Never reuse or move a published tag.

## Workflow setup

The release workflow uses the built-in `GITHUB_TOKEN` with contents,
pull-requests and issues write permissions. No PAT is required. Enable
**Settings → Actions → General → Workflow permissions → Allow GitHub Actions
to create and approve pull requests**, subject to organization policy.

Generated release PR workflows require a maintainer to select **Approve
workflows to run** and wait for the checks. Bot updates may need approval again.
Bot push/tag/release events do not automatically start other workflows; see
[GitHub's workflow triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow).

HACS also requires a non-empty repository description, topics and a detected
license. Do not bypass those checks with ignores. The source uses MIT; brands
is the only current HACS ignore, pending installed validation.

## Publish and recover

1. Review the Release Please PR: version, notes, compatibility, migrations and
   acceptance evidence. Preserve its generated metadata and lifecycle labels.
2. Approve its workflows, wait for candidate checks and merge after review.
3. Release Please creates a draft GitHub release. Check the tag target, manifest
   version and main CI on that exact SHA. Obtain maintainer release authorization
   before publishing. Complete the fresh HACS install check above.
4. If automation fails, inspect permissions, workflow approvals and existing
   PRs/drafts, then rerun Release Please on main. Preserve published tags.
5. For rollback, reinstall a previously validated version and restart HA. If none
   exists, remove the integration and preserve HA backups. Withdraw the faulty
   release and publish a fix with a higher version.
