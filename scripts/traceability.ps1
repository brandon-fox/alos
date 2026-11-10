param([Parameter(Mandatory=$true)][string]$Repo, [string]$FeaturesDir = 'tests\features', [string]$Out = 'docs\traceability.md')
Set-Location $Repo
$specDirs = Get-ChildItem specs -Directory | Where-Object { $_.Name -match '^\d{3}-' } | Sort-Object Name
$features = @(Get-ChildItem $FeaturesDir -File -Filter *.feature -ErrorAction SilentlyContinue)
$adrs = @(Get-ChildItem docs\adr -File -Filter *.md -ErrorAction SilentlyContinue)
$rows = @()
$gaps = 0
foreach ($d in $specDirs) {
  $num = $d.Name.Substring(0,3)
  $slug = $d.Name.Substring(4)
  $hasSpec = Test-Path (Join-Path $d.FullName 'spec.md')
  $hasPlan = Test-Path (Join-Path $d.FullName 'plan.md')
  $hasTasks = Test-Path (Join-Path $d.FullName 'tasks.md')
  $words = ($slug -split '-') | Where-Object { $_.Length -gt 3 }
  $feat = $features | ForEach-Object { $n = $_.BaseName; $hits = @($words | Where-Object { $n -like "*$_*" }); $long = @($hits | Where-Object { $_.Length -ge 7 }); [pscustomobject]@{ F = $_; Score = $hits.Count + $long.Count } } | Where-Object { $_.Score -ge 2 } | Sort-Object Score -Descending | Select-Object -First 1 -ExpandProperty F
  $adr = $adrs | Where-Object { $n = $_.BaseName; (($words | Where-Object { $n -like "*$_*" }).Count -ge 2) } | Select-Object -First 1
  $featCell = if ($feat) { "[$($feat.Name)](../$($FeaturesDir.Replace('\','/'))/$($feat.Name))" } else { $gaps++; "none" }
  $adrCell = if ($adr) { "[$($adr.BaseName.Substring(0, [Math]::Min(40, $adr.BaseName.Length)))](adr/$($adr.Name))" } else { "none" }
  $mark = { param($b) if ($b) { 'yes' } else { 'no' } }
  $rows += ("| [$($d.Name)](../specs/$($d.Name)/) | {0} | {1} | {2} | {3} | {4} |" -f (& $mark $hasSpec), (& $mark $hasPlan), (& $mark $hasTasks), $featCell, $adrCell)
}
$date = Get-Date -Format 'yyyy-MM-dd'
$header = @"
# Traceability

> Generated $date by ``scripts/traceability.ps1`` from ``specs/``, ``$($FeaturesDir.Replace('\','/'))/`` and ``docs/adr/``. Regenerate rather than edit. A feature with no acceptance file is a gap, listed as ``none``; $gaps of $($specDirs.Count) specs have no matched feature file today.

Matching is by shared slug words (two words, or one word of seven or more letters); a row marked ``none`` may have coverage under a different name. The honest reading is the gap count, not the match count.

| Spec | spec.md | plan.md | tasks.md | Acceptance feature | ADR |
| --- | --- | --- | --- | --- | --- |
"@
$content = $header + "`n" + ($rows -join "`n") + "`n"
$outPath = Join-Path $Repo $Out
[IO.File]::WriteAllText($outPath, $content, (New-Object Text.UTF8Encoding($false)))
Write-Output ("specs={0} features={1} adrs={2} gaps={3} -> {4}" -f $specDirs.Count, $features.Count, $adrs.Count, $gaps, $Out)
