# Requirements Verification Checklist: GitHub Actions Expansion

- [x] **FR-001**: Gitleaks secret scanning workflow (`security-compliance.yml`)
- [x] **FR-002**: OpenSSF Scorecard posture audit (`security-compliance.yml`)
- [x] **FR-003**: GitHub CodeQL SAST scanning for Python and Rust (`security-compliance.yml`)
- [x] **FR-004**: Python wheel packaging & twine check (`release-packaging.yml`)
- [x] **FR-005**: Rust native release binary build validation (`release-packaging.yml`)
- [x] **FR-006**: Multi-arch Docker buildx & SBOM generation (`release-packaging.yml`)
- [x] **FR-007**: Automated release notes drafting (`release-packaging.yml`)
- [x] **FR-008**: SpecKit directory matrix audit (`speckit-governance.yml`)
- [x] **FR-009**: ADR repository integrity check (`speckit-governance.yml`)
- [x] **FR-010**: Performance benchmarking workflow (`performance-benchmark.yml`)
- [x] **FR-011**: `uv lock --check` and license audit in `quality-gate.yml`
- [x] **FR-012**: `cargo fmt --check` and `cargo audit` in `rust-ci.yml`
- [x] **SC-001**: `tests/test_github_workflows.py` passes all YAML validation tests
