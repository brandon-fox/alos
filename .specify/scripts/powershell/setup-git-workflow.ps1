# PowerShell script to set up ALOS Git workflow and branch configuration

$ErrorActionPreference = "Stop"

Write-Host "[1/3] Checking current Git branch status..." -ForegroundColor Cyan
$currentBranch = (git branch --show-current).Trim()

if ($currentBranch -eq "master") {
    Write-Host "Renaming local 'master' branch to 'main'..." -ForegroundColor Yellow
    git branch -m master main
    Write-Host "Renamed local branch to 'main'." -ForegroundColor Green
} else {
    Write-Host "Current branch: $currentBranch" -ForegroundColor Green
}

Write-Host "[2/3] Checking Git SSH commit signing configuration..." -ForegroundColor Cyan
$gpgFormat = git config --get gpg.format
$signingKey = git config --get user.signingkey

if (-not $gpgFormat) {
    Write-Host "Setting gpg.format=ssh..." -ForegroundColor Yellow
    git config --local gpg.format ssh
}

if (-not $signingKey) {
    $sshKeyPath = "$HOME\.ssh\id_ed25519.pub"
    if (Test-Path $sshKeyPath) {
        Write-Host "Setting user.signingkey=$sshKeyPath..." -ForegroundColor Yellow
        git config --local user.signingkey $sshKeyPath
        git config --local commit.gpgsign true
        Write-Host "Git commit signing configured with $sshKeyPath" -ForegroundColor Green
    } else {
        Write-Host "Warning: No default SSH public key found at $sshKeyPath. Please configure 'git config user.signingkey <path-to-pubkey>'." -ForegroundColor Yellow
    }
} else {
    Write-Host "Git signing key already configured: $signingKey" -ForegroundColor Green
}

Write-Host "[3/3] Checking Git hygiene and cache rules..." -ForegroundColor Cyan
$cacheFiles = git ls-files | Select-String -Pattern "__pycache__|\.pyc$"
if ($cacheFiles) {
    Write-Host "Warning: Pycache files detected in git index. Removing from index..." -ForegroundColor Yellow
    git rm --cached -r **/__pycache__/ 2>$null
    git rm --cached *.pyc 2>$null
} else {
    Write-Host "Git index is clean of pycache artifacts." -ForegroundColor Green
}

Write-Host "`nGit workflow setup complete!" -ForegroundColor Green
