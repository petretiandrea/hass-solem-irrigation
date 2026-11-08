# Branding and dependency provenance

Audit date: 2026-11-07. Source baseline: `f1902d3`.
This audit records source and build evidence plus unresolved provenance.

## Brand assets

The [brands tree at db0aad8](https://github.com/home-assistant/brands/tree/db0aad8a331dbe60417caaebf9f7f18480565151)
has no `solem_woobee` directory in either integration namespace. It does contain
identical SOLEM icons under `custom_integrations/solem_toolkit` and
`custom_integrations/solem_bluetooth_watering_controller`.

The integration includes unchanged upstream SOLEM icons in `custom_components/solem_woobee/brand/`. The [2026.3 announcement](https://contributors.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
and [brands README](https://github.com/home-assistant/brands/blob/db0aad8a331dbe60417caaebf9f7f18480565151/README.md)
direct custom integrations to this local layout rather than a new legacy
`custom_integrations/` submission. Our minimum HA 2026.8.0 supports it.
The square icon doubles as the logo through HA's documented fallback.

Asset source: `custom_integrations/solem_toolkit/` at the brands revision above:

| File | Dimensions | SHA-256 |
| --- | --- | --- |
| icon.png | 256 × 256 | `1ffd7541b630f15f582c4c3ef128d38c536cd9c2776a3caa0653aa351d2b35b9` |
| icon@2x.png | 512 × 512 | `4d2adbc17cd121827575b9339c0f935d6fe267a3bc7276a0d0bbf2c29503aa65` |

The images identify SOLEM; trademarks remain their owners' property, with no
endorsement implied. They are reused from the HA brands identification assets,
not newly authored project artwork or covered by this project's MIT grant.

Installed branding remains unverified. Keep `brands: todo` and the HACS brands
ignore until candidate checks and an installed HA check pass. Verify icon/logo
in light/dark themes at normal/HiDPI resolution and inspect the authenticated
`/api/brands/integration/solem_woobee/icon.png` and logo endpoints. Record the
candidate SHA, HA version and results.

## Distribution

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
| woobee_api | integration manifest version | integration manifest version | embedded source in this repository |

Verified against the tagged HA [2026.8.0 Bluetooth manifest](https://github.com/home-assistant/core/blob/2026.8.0/homeassistant/components/bluetooth/manifest.json),
[2026.10.4 Bluetooth manifest](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/bluetooth/manifest.json),
and base requirements for [2026.8.0](https://github.com/home-assistant/core/blob/2026.8.0/requirements.txt)
and [2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/requirements.txt).
HA resolves these packages and their transitive dependencies.

Local `pip install -e .` instead resolves `bleak>=0.22` and `cryptography>=42`
from pyproject. Capture resolved versions with `pip freeze` for standalone release reviews.
Hatchling, pytest, Ruff and test plugins are development tools.

## License, source, tag and public build audit

The [dependency-transparency rule](https://contributors.home-assistant.io/core/quality-scale/dependency-transparency/)
requires OSI licensing, PyPI distribution, matching public tags and public CI
build/publication. Evidence for the versions actually supplied by our HA matrix:

| Package | License and versioned source | Public build/publication |
| --- | --- | --- |
| Bleak 3.0.2 | MIT; [tag v3.0.2](https://github.com/hbldh/bleak/tree/v3.0.2), LICENSE at that tag; [PyPI](https://pypi.org/project/bleak/3.0.2/) has wheel and sdist | [release workflow](https://github.com/hbldh/bleak/blob/v3.0.2/.github/workflows/pypi-publish.yml) builds with uv and uploads with Twine on published releases |
| cryptography 48.0.1 | Apache-2.0 OR BSD-3-Clause; [tag](https://github.com/pyca/cryptography/tree/48.0.1), LICENSE/ LICENSE.APACHE/ LICENSE.BSD; [PyPI](https://pypi.org/project/cryptography/48.0.1/) has 49 files | [wheel builder](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/wheel-builder.yml), [publisher](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/pypi-publish.yml): tag builds, artifact transfer and trusted publication |
| cryptography 50.0.1 | same dual license; [tag](https://github.com/pyca/cryptography/tree/50.0.1); [PyPI](https://pypi.org/project/cryptography/50.0.1/) has 46 files | [wheel builder](https://github.com/pyca/cryptography/blob/50.0.1/.github/workflows/wheel-builder.yml), [publisher](https://github.com/pyca/cryptography/blob/50.0.1/.github/workflows/pypi-publish.yml): same public pipeline, with attestations |

The audit checked versioned source, licenses, build workflows and PyPI records;
it did not reproduce the published binaries. No dependency payload is vendored.

## Protocol origin: unresolved evidence

`LICENSE` and pyproject SPDX metadata license project source under MIT. The
embedded client has no independent tagged release or PyPI publishing pipeline.

[Client documentation](client.md), [research](research/solem-woobee-wb4-home-assistant.md)
and module docstrings
attribute transport/frames to static reverse engineering of MySOLEM 6.13.3,
including Java parser logic and `configIrriV5()`. Related BL-IP projects are
research references, not evidence of the WooBee client’s origin.

Before release, record APK acquisition URL/date, checksum, tool versions and
a derivation inventory separating protocol facts from copied or translated code.
Review rights and required notices for third-party material. Keep APK/decompiled
source outside this repository; the project MIT license cannot grant those rights.

## Distribution decision

Dependency transparency remains TODO: HA dependency evidence is recorded above,
but client derivation and release provenance are incomplete. Embedding the client
does not satisfy Core’s external-library publication requirements.

If Core contribution is pursued, decide separately whether to extract the client
into a reusable external library. That decision must assign ownership/name,
resolve derivation licensing, define API and version compatibility, preserve
simulated BLE tests, and add tagged public CI builds plus PyPI publication with
reviewable artifacts. Before implementing it, explicitly replace/reconcile the
embedded requirement assertion and no-PyPI publisher gate in
`scripts/check_distribution.py`, Hatch package/version configuration,
manifest exact requirement pin, imports, CI and `docs/releasing.md`. Plan a
custom-user migration and rollback; do not silently remove these gates or publish
a package as routine maintenance.

## HACS audit result

On 2026-11-07, GitHub reads confirmed a description, HACS/HA/irrigation topics
and detected MIT license. [HACS run 42379421457](https://github.com/petretiandrea/hass-solem-irrigation/actions/runs/42379421457)
and [test run 42379421458](https://github.com/petretiandrea/hass-solem-irrigation/actions/runs/42379421458)
passed for `f1902d3`. HACS ignored brands. These historical checks resolve the
earlier missing-metadata reports, but do not validate installed branding or a
clean installation of a release.
