<#
.SYNOPSIS
    Mandatory local ALOS pre-handback validation suite (concurrent cross-platform wrapper).
.DESCRIPTION
    Delegates to scripts/run_validation_suite.py to execute lock verification, Ruff lint/format,
    Mypy static typing, Bandit AST scan, pyadr governance, parallel Pytest unit/meta/contention/fuzz
    coverage suite, parallel Mocked Behave BDD suite, and serialized Live Behave BDD suite.
#>
param(
    [switch]$SkipLive,
    [switch]$RequireLive,
    [int]$CovFailUnder = 90
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PyArgs = @("scripts/run_validation_suite.py", "--cov-fail-under", "$CovFailUnder")
if ($SkipLive) {
    $PyArgs += "--skip-live"
}
if ($RequireLive) {
    $PyArgs += "--require-live"
}

& uv run python @PyArgs
if ($LASTEXITCODE -ne 0) {
    throw "Validation suite failed (exit code $LASTEXITCODE)"
}
