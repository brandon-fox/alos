<#
.SYNOPSIS
    SpecKit Lifecycle Management Tool.
.DESCRIPTION
    Validates and updates feature specification state transitions.
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$FeatureName,

    [Parameter(Mandatory=$false)]
    [string]$Action = "status",

    [Parameter(Mandatory=$false)]
    [string]$TargetState
)

$ErrorActionPreference = "Stop"

Write-Host "[SpecKit Lifecycle] Feature: $FeatureName | Action: $Action | TargetState: $TargetState"

# Delegate execution to Python alos.cli engine if available
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    if ($FeatureName) {
        python -m alos.cli speckit lifecycle --feature $FeatureName --action $Action --target-state $TargetState
    } else {
        python -m alos.cli speckit lifecycle --action $Action
    }
} else {
    Write-Host "[SpecKit Lifecycle] Python CLI engine not found. Completed lifecycle script wrapper."
}
