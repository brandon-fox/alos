<#
.SYNOPSIS
    Mandatory local ALOS pre-handback validation suite.
.DESCRIPTION
    Executes lock verification, Ruff lint/format, Mypy static typing, Bandit AST scan,
    pyadr governance, full Pytest unit/coverage suite, Mocked Behave BDD suite, and
    Live Hardware/Ollama Behave BDD integration suite before any manual stage or hand-back.
#>
param(
    [switch]$SkipLive
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-Gate {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "`n==> [$Label]" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Validation gate failed: $Label (exit code $LASTEXITCODE)"
    }
}

try {
    Invoke-Gate "1/8 uv.lock sync check" { uv lock --check }
    Invoke-Gate "2/8 Ruff format check" { uv run ruff format --check alos tests features alembic }
    Invoke-Gate "3/8 Ruff lint check" { uv run ruff check alos tests features alembic }
    Invoke-Gate "4/8 Mypy static type check" { uv run mypy alos tests features }
    Invoke-Gate "5/8 Bandit security scan" { uv run bandit -r alos -s B101 -q }
    Invoke-Gate "6/8 pyadr ADR sanity check" { uv run pyadr check-adr-repo --no-ansi }
    Invoke-Gate "7/8 Pytest full unit, meta & coverage suite (>=85%)" {
        uv run python scripts/run_pytest_clean.py --cov=alos --cov-report=term-missing --cov-fail-under=85 -q
    }
    Invoke-Gate "8a/8 Behave BDD - Mocked scenarios (@mocked)" {
        uv run behave --tags="@mocked"
    }
    if (-not $SkipLive) {
        Invoke-Gate "8b/8 Behave BDD - Live hardware & Ollama integration (@live)" {
            uv run behave --tags="@live"
        }
    }
    Write-Host "`nALL VALIDATION GATES PASSED." -ForegroundColor Green
}
finally {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $RepoRoot ".pytest_tmp")
}
