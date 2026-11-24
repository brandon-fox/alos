param([Parameter(Mandatory=$true)][string]$Repo, [string]$FeaturesDir = 'tests/features', [string]$Out = 'docs/traceability.md')
$ErrorActionPreference = 'Stop'
& uv run python (Join-Path $PSScriptRoot 'traceability.py') --repo $Repo --features-dir $FeaturesDir --out $Out
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
