# Adopt Release Please Maturin Sccache and GitHub OIDC SLSA Provenance Over Custom Release Scripts

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/038-enterprise-cicd-pipeline/spec.md`

## Context and Problem Statement

ALOS currently has zero git tags and zero GitHub Releases:
1. Version `0.1.0` is hardcoded across `pyproject.toml`, `crates/alos_native/Cargo.toml`, `sonar-project.properties`, and `CITATION.cff`, while `post-merge-pipeline.yml` clobbers `CHANGELOG.md` from scratch (`chore/bot-changelog`).
2. `release-packaging.yml` runs `uv build` (producing a pure-Python wheel without the `alos_native` Rust PyO3 extension), uploads raw `target/release/` intermediates, skips isolated venv smoke tests, hardcodes `push: false` on Docker images even on `v*` tags, and produces zero `SHA256SUMS.txt` or SLSA provenance attestations.
3. Writing a custom SemVer parser, changelog generator, and multi-OS wheel builder in bespoke Python scripts would duplicate mature open-source release tooling and increase maintenance burden.

Which upstream, zero-bloat release automation and supply-chain attestation stack should ALOS adopt?

## Decision Drivers

* **Zero Custom Release Code**: Use declarative config (`release-please-config.json` + `.release-please-manifest.json` `extra-files`) to keep all 4 versioned files and Keep-a-Changelog `CHANGELOG.md` in lockstep via vetted PRs without granting bots ruleset bypass rights.
* **Immune to `GITHUB_TOKEN` Event Suppression**: Chain `release-please` (`outputs.release_created == 'true'`) directly into `release-packaging.yml` via `workflow_call` (plus `workflow_run` fallback on `main` merges) so releases build and publish reliably even without a PAT.
* **Fast Cached Cross-Platform Packaging & Cryptographic Provenance**: Compile native `alos_native` wheels via `PyO3/maturin-action` (`sccache: true`), push multi-arch non-root GHCR images (`scope=alos-runtime` BuildKit cache), and emit CycloneDX SBOMs + GitHub OIDC `actions/attest-build-provenance` SLSA attestations.

## Considered Options

* Option 1: `googleapis/release-please-action` (`extra-files` lockstep PRs) chaining via `workflow_call` into `PyO3/maturin-action` (`sccache: true`) + multi-arch GHCR + `anchore/sbom-action` + `actions/attest-build-provenance`
* Option 2: Custom Python `cut_release.py` SemVer/changelog/manifest engine + manual `cargo build --release` matrix
* Option 3: `python-semantic-release` pushing version commits and tags directly onto `main` via a bypass actor token

## Decision Outcome

Chosen option: "Option 1: `googleapis/release-please-action` (`extra-files` lockstep PRs) chaining via `workflow_call` into `PyO3/maturin-action` (`sccache: true`) + multi-arch GHCR + `anchore/sbom-action` + `actions/attest-build-provenance`", because `release-please` natively updates TOML/YAML/properties `extra-files` and `CHANGELOG.md` via standard PRs (respecting `bypass_actors: []` on `main`), direct `workflow_call` chaining eliminates `GITHUB_TOKEN` tag-trigger deadlocks, `maturin-action` with `sccache` builds cached cross-OS PyO3 wheels out of the box, and GitHub OIDC SLSA provenance requires zero static signing keys.

### Positive Consequences

* Zero custom Python release-bump or changelog code to write, test, or maintain; retires `post-merge-pipeline.yml`'s destructive `generate-changelog` job.
* Every release publishes clean-venv smoke-tested Python sdist + cross-OS `alos_native` wheels, non-root multi-arch `ghcr.io/brandon-fox/alos` images, `SHA256SUMS.txt`, CycloneDX SBOMs, and SLSA provenance verifiable via `gh attestation verify`.
* Enforces `PR_TITLE` squash commits on `main` so `release-please` always receives validated Conventional Commit headers.

### Negative Consequences

* `sonar-project.properties` requires a one-line `# x-release-please-version` annotation comment so `release-please`'s `generic` updater can bump `sonar.projectVersion` deterministically.

## Pros and Cons of the Options

### Option 1: `release-please` + `workflow_call` + `PyO3/maturin-action` (`sccache`) + GHCR + OIDC SLSA

* Good, because 100% declarative JSON config replaces hundreds of lines of custom SemVer/changelog Python code.
* Good, because `sccache` + `Swatinem/rust-cache` accelerates cross-OS Rust wheel compilation and `workflow_call` works with default `GITHUB_TOKEN`.
* Bad, because release cuts happen in two clean PR merges (feature PR -> `chore(main): release X.Y.Z` PR) rather than direct commits to `main`.

### Option 2: Custom Python `cut_release.py` + manual `cargo build`

* Good, because customizable in Python.
* Bad, because reinvents Conventional Commit parsing, Keep-a-Changelog rendering, and wheel ABI tagging (`manylinux`) already solved upstream.

### Option 3: Direct-push `semantic-release` bypassing `main` branch protection

* Good, because cuts a release on every merge without a release PR.
* Bad, because violates `bypass_actors: []` on `main` and prevents human/CI vetting of release notes and version bumps before tagging.

## Links

* Refines [ADR-0012](0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md) and [ADR-0018](0018-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md)
* Complements [ADR-0026](0026-consolidate-ci-workflows-into-cached-groups-behind-unified-merge-gate-and-declarative-rulesets.md)
