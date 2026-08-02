<#
.SYNOPSIS
    SpecKit Feature Archiving Tool.
.DESCRIPTION
    Archives a completed or deprecated feature specification directory into specs/archive/.
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$FeatureName,

    [Parameter(Mandatory=$false)]
    [switch]$Restore
)

$ErrorActionPreference = "Stop"

if ($Restore) {
    Write-Host "[SpecKit Archive] Restoring feature: $FeatureName"
    python -m alos.cli speckit archive --feature $FeatureName --restore
} else {
    Write-Host "[SpecKit Archive] Archiving feature: $FeatureName"
    python -m alos.cli speckit archive --feature $FeatureName
}
