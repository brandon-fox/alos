# PowerShell script to set up ALOS development environment and git hooks

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Checking Python and uv installation..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'uv' is not installed. Please install uv first." -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] Syncing virtual environment and installing dev dependencies..." -ForegroundColor Cyan
uv pip install -e ".[dev]"

Write-Host "[3/4] Installing pre-commit hooks..." -ForegroundColor Cyan
if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
    pre-commit install
    pre-commit install --hook-type pre-push
    Write-Host "Pre-commit and pre-push hooks installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Warning: pre-commit command not found in PATH." -ForegroundColor Yellow
}

Write-Host "[4/4] Verifying code quality tools..." -ForegroundColor Cyan
uv run ruff --version
uv run mypy --version
uv run bandit --version
uv run pytest --version

Write-Host "`nALOS dev environment setup complete!" -ForegroundColor Green
