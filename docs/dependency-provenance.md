# Branding and dependency provenance (SBR-100)

Audit date: 2026-11-07. Source baseline: current main `f1902d3`.
This is a custom distribution review, not an official Quality Scale tier claim.

## Branding outcome

The complete, non-truncated [brands tree at db0aad8](https://github.com/home-assistant/brands/tree/db0aad8a331dbe60417caaebf9f7f18480565151)
has no `solem_woobee` directory in either integration namespace. It does contain
identical SOLEM icons under `custom_integrations/solem_toolkit` and
`custom_integrations/solem_bluetooth_watering_controller`.

This PR prepares the custom-integration alternative: unchanged upstream SOLEM
icons in `custom_components/solem_woobee/brand/`. The [2026.3 announcement](https://contributors.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
and [brands README](https://github.com/home-assistant/brands/blob/db0aad8a331dbe60417caaebf9f7f18480565151/README.md)
direct custom integrations to this local layout rather than a new legacy
`custom_integrations/` submission. Our minimum HA 2026.8.0 supports it.
The square icon doubles as the logo through HA's documented fallback.
No `core_integrations/solem_woobee` submission is appropriate for this custom
integration. A future Core contribution needs its own upstream brands review.

Asset source: `custom_integrations/solem_toolkit/` at the brands revision above:

| File | Dimensions | SHA-256 |
| --- | --- | --- |
| icon.png | 256 × 256 | `1ffd7541b630f15f582c4c3ef128d38c536cd9c2776a3caa0653aa351d2b35b9` |
| icon@2x.png | 512 × 512 | `4d2adbc17cd121827575b9339c0f935d6fe267a3bc7276a0d0bbf2c29503aa65` |

The images identify SOLEM; trademarks remain their owners' property, with no
endorsement implied. They are reused from the HA brands identification assets,
not newly authored project artwork or covered by this project's MIT grant.

The [Core brands rule](https://contributors.home-assistant.io/core/quality-scale/brands/)
still requires upstream assets and has no exemption. Keep `brands: todo` and
HACS `ignore: brands` until candidate validation and an installed HA check prove
the custom route works, or an upstream domain submission is accepted. A prepared
local asset set is not evidence that either check passed. Verify the installed
integration icon and logo in light/dark themes at normal/HiDPI resolution; inspect
`/api/brands/integration/solem_woobee/icon.png` and the logo endpoint with HA
authentication. Record candidate SHA/HA version and HACS results before removing
the ignore. Do not use placeholder-fallback CDN URLs as proof of upstream assets.

## What is actually distributed

HACS copies this component's source tree, including `woobee_api` and brand images.
It does not install this repository's pyproject or distribute Bleak/cryptography
wheels. `manifest.json` has `requirements: []` and `dependencies: ["bluetooth"]`.
The client imports Bleak and cryptography; they are real external dependencies,
even though HA supplies them. Empty manifest requirements alone are not grounds
for a dependency-transparency exemption.

| Dependency | HA 2026.8.0 | HA 2026.10.4 | Ownership |
| --- | --- | --- | --- |
| bleak | 3.0.2 | 3.0.2 | HA Bluetooth manifest requirement |
| cryptography | 48.0.1 | 50.0.1 | HA base requirements.txt |
| woobee_api | integration version 0.1.0 | integration version 0.1.0 | embedded source in this repository |

Verified against the tagged HA [2026.8.0 Bluetooth manifest](https://github.com/home-assistant/core/blob/2026.8.0/homeassistant/components/bluetooth/manifest.json),
[2026.10.4 Bluetooth manifest](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/bluetooth/manifest.json),
and base requirements for [2026.8.0](https://github.com/home-assistant/core/blob/2026.8.0/requirements.txt)
and [2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/requirements.txt).
HA owns the resolution and transitive packages of those dependencies; this is not
a claim to have audited every HA wheel, native OpenSSL build or OS BLE backend.

Local `pip install -e .` instead resolves `bleak>=0.22` and `cryptography>=42`
from pyproject. These unbounded ranges are development inputs, not a lock or a
claim that every possible resolved version was audited. Capture `pip freeze`
for any standalone build/release review. Hatchling is the local build backend;
pytest/Ruff/test plugins are development tools, not HACS payload dependencies.

## License, source, tag and public build audit

The [dependency-transparency rule](https://contributors.home-assistant.io/core/quality-scale/dependency-transparency/)
requires OSI licensing, PyPI distribution, matching public tags and public CI
build/publication. Evidence for the versions actually supplied by our HA matrix:

| Package | License and versioned source | Public build/publication |
| --- | --- | --- |
| Bleak 3.0.2 | MIT; [tag v3.0.2](https://github.com/hbldh/bleak/tree/v3.0.2), LICENSE at that tag; [PyPI](https://pypi.org/project/bleak/3.0.2/) has wheel and sdist | [release workflow](https://github.com/hbldh/bleak/blob/v3.0.2/.github/workflows/pypi-publish.yml) builds with uv and uploads with Twine on published releases |
| cryptography 48.0.1 | Apache-2.0 OR BSD-3-Clause; [tag](https://github.com/pyca/cryptography/tree/48.0.1), LICENSE/ LICENSE.APACHE/ LICENSE.BSD; [PyPI](https://pypi.org/project/cryptography/48.0.1/) has 49 files | [wheel builder](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/wheel-builder.yml), [publisher](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/pypi-publish.yml): tag builds, artifact transfer and trusted publication |
| cryptography 50.0.1 | same dual license; [tag](https://github.com/pyca/cryptography/tree/50.0.1); [PyPI](https://pypi.org/project/cryptography/50.0.1/) has 46 files | [wheel builder](https://github.com/pyca/cryptography/blob/50.0.1/.github/workflows/wheel-builder.yml), [publisher](https://github.com/pyca/cryptography/blob/50.0.1/.github/workflows/pypi-publish.yml): same public pipeline, with attestations |

PyPI version JSON and versioned upstream workflow/license files were fetched
successfully during this audit. This establishes public source/tag/build paths;
it is not a cryptographic reproduction of uploaded binaries or verification of
each individual publish run. No package payload is vendored into this component.

## Embedded client and protocol origin: unresolved evidence

`LICENSE` and pyproject SPDX metadata grant MIT licensing for project source;
GitHub currently detects MIT. The historical missing-source-license finding is
resolved. Git history begins with `20b77a8` (BLE client), `c23f095` (controller
management), then `b585254` (embedded consolidation). There is no independently
released client artifact, tagged client release or PyPI publishing pipeline.
The manifest's 0.1.0 value does not establish a published release.

README, `docs/research/solem-woobee-wb4-home-assistant.md`, and module docstrings
attribute transport/frames to static reverse engineering of MySOLEM 6.13.3,
including Java parser logic and `configIrriV5()`. The research refers to a local
`MySOLEM.apk`; the tracked tree contains no APK provenance record with acquisition
URL/date, checksum, tool versions or a derivation inventory distinguishing
interoperability facts from translated/copied expression. Related BL-IP projects
are research references, not proof of a licensed WooBee client origin.

Remaining blocker: maintainer must record that acquisition/derivation evidence
and establish rights/required notices for any copied or translated material.
The project MIT license cannot grant third-party rights. Do not redistribute
APK/decompiled source to fill this gap. Record a factual origin inventory and
review outcome before the first release; do not assert clean-room development,
vendor authorization or a legal conclusion from the existing evidence.

## Custom outcome and separate Core migration proposal

Retain dependency-transparency TODO. HA-provided dependency versions have public
license/source/tag/build evidence; embedded-client derivation and release
provenance remain incomplete. Custom source distribution is intentional and
reviewable, but does not satisfy all of the Core rule's PyPI/publication conditions
or justify the no-external-dependencies exception. No architecture change is
implemented here and first-release provenance approval remains pending.

If Core contribution is pursued, decide separately whether to extract the client
into a reusable external library. That decision must assign ownership/name,
resolve derivation licensing, define API and version compatibility, preserve
simulated BLE tests, and add tagged public CI builds plus PyPI publication with
reviewable artifacts. Before implementing it, explicitly replace/reconcile the
embedded requirement assertion and no-PyPI publisher gate in
`scripts/check_distribution.py`, Hatch package/version configuration,
manifest exact requirement pin, imports, CI and `docs/releasing.md`. Plan a
custom-user migration and rollback; do not silently remove these gates or publish
a package under this issue. No Core packaging exemption is asserted.

## Fresh HACS metadata recheck

Authenticated GitHub reads succeeded on 2026-11-07. Repository description is
non-empty, topics include `hacs`, `hacs-integration`, `home-assistant`,
`irrigation`, `solem-woobee`, and detected license is MIT.
[Main HACS run 42379421457](https://github.com/petretiandrea/hass-solem-irrigation/actions/runs/42379421457)
completed successfully for f1902d3, following the historical failed PR run
42378651756. [Main tests run 42379421458](https://github.com/petretiandrea/hass-solem-irrigation/actions/runs/42379421458)
also succeeded. These fresh results supersede the SBR-96 metadata failures and
403 access reports. HACS still ignores brands; success does not resolve that rule
or prove an installed icon, published release or clean installation.
