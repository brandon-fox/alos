#!/usr/bin/env pwsh
# Validate SpecKit specifications and ADR adherence
[CmdletBinding()]
param(
    [switch]$Help
)
$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Host "Usage: .\.specify\scripts\powershell\validate-specs.ps1"
    Write-Host "Validates that all directories under specs/ adhere to the canonical 3-digit NNN-feature layout,"
    Write-Host "contain required files (spec.md, plan.md, tasks.md, checklists/requirements.md), and valid ADR links."
    exit 0
}

$repoRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
$specsDir = Join-Path $repoRoot "specs"
$adrDir = Join-Path $repoRoot "docs/adr"

if (-not (Test-Path $specsDir)) {
    Write-Error "Error: specs directory not found at $specsDir"
    exit 1
}

$errors = @()
$seenNumbers = @{}
$allowedNonSpecDirs = @('personas')

$specDirectories = Get-ChildItem -Path $specsDir -Directory | Where-Object { $allowedNonSpecDirs -notcontains $_.Name }

foreach ($dir in $specDirectories) {
    $dirName = $dir.Name

    # 1. Enforce NNN-feature format (3-digit zero-padded prefix)
    if ($dirName -notmatch '^\d{3}-[a-z0-9-]+$') {
        $errors += "Directory '$dirName' does not match the canonical 3-digit format 'NNN-feature-name' (e.g., '001-feature-name')."
        continue
    }

    # 2. Check for duplicate indices
    $num = $matches[0].Substring(0, 3)
    if ($seenNumbers.ContainsKey($num)) {
        $errors += "Duplicate spec number '$num' found in directory '$dirName' (conflicts with '$($seenNumbers[$num])')."
    } else {
        $seenNumbers[$num] = $dirName
    }

    # 3. Required files check
    $requiredFiles = @('spec.md', 'plan.md', 'tasks.md', 'checklists/requirements.md')
    foreach ($reqFile in $requiredFiles) {
        $filePath = Join-Path $dir.FullName $reqFile
        if (-not (Test-Path $filePath)) {
            $errors += "Spec directory '$dirName' is missing required file: '$reqFile'."
        }
    }

    # 4. ADR Link Verification
    $specMd = Join-Path $dir.FullName "spec.md"
    if (Test-Path $specMd) {
        $content = Get-Content -Path $specMd -Raw
        $adrMatches = [regex]::Matches($content, 'ADR[-\s]?(\d{4})')
        foreach ($match in $adrMatches) {
            $adrNum = $match.Groups[1].Value
            $matchingAdr = Get-ChildItem -Path $adrDir -File | Where-Object { $_.Name -match "^$adrNum-" }
            if (-not $matchingAdr) {
                $errors += "Spec '$dirName' references ADR $adrNum, but no matching ADR file was found in '$adrDir'."
            }
        }
    }
}

if ($errors.Count -gt 0) {
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host " SpecKit Specification Validation Errors" -ForegroundColor Red
    Write-Host "=========================================" -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host "  - $err" -ForegroundColor Red
    }
    Write-Host "Validation failed with $($errors.Count) error(s)." -ForegroundColor Red
    exit 1
}

Write-Host "SpecKit specification validation passed: $($specDirectories.Count) spec(s) verified clean." -ForegroundColor Green
exit 0
