# Quality & Compliance Checklist: Open-Source Core & Dual-Repo Architecture

## Quality Gates & Verification
- [ ] `pyadr check-adr-repo` passes cleanly with zero errors.
- [ ] `pytest` passes 100% of unit and BDD feature tests.
- [ ] `ruff check alos tests` passes with zero linting errors.
- [ ] `mypy alos tests` passes with zero type check errors.
- [ ] `.env` is absent from git tracking (`git status` shows `.env` ignored).
- [ ] `.github/workflows/ci.yml` is valid YAML syntax.
