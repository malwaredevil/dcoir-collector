[CmdletBinding()]
param(
    [string]$RepoRoot = $env:DCOIR_REPO_ROOT,
    [string]$OutputDir = $env:DCOIR_DOWNLOADS_DIR,
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$StashMessagePrefix = "pre-pull-local-work"
)

$ErrorActionPreference = "Continue"
$gitModule = Join-Path $PSScriptRoot '..\modules\Dcoir.Git\Dcoir.Git.psd1'
$gitModule = (Resolve-Path -LiteralPath $gitModule).Path
Import-Module -Name $gitModule -Force -Global -ErrorAction Stop

$cmdGetEnv = Get-Command -Name 'Get-DcoirGitSystemEnvValue' -ErrorAction Stop
$cmdAddLine = Get-Command -Name 'Add-DcoirGitUtf8Line' -ErrorAction Stop
$cmdGit = Get-Command -Name 'Invoke-DcoirGitCommand' -ErrorAction Stop

if (-not $RepoRoot) { $RepoRoot = & $cmdGetEnv -Name 'DCOIR_REPO_ROOT' -Required }
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw "Repo root not found: $RepoRoot" }
if (-not $OutputDir) { $OutputDir = & $cmdGetEnv -Name 'DCOIR_DOWNLOADS_DIR' -Required }
if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) { New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null }

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $OutputDir "dcoir_safe_prepull_apply_$stamp.txt"

function Write-PrePullLine {
    param([AllowEmptyString()][string]$Text)
    Write-Host $Text
    & $cmdAddLine -Path $log -Text $Text
}

function Invoke-PrePullGit {
    param([Parameter(Mandatory=$true)][string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)
    return & $cmdGit -RepoRoot $RepoRoot -Arguments $Arguments -LogPath $log -AllowFailure:$AllowFailure -Quiet:$Quiet
}

function Get-StashHead {
    $result = Invoke-PrePullGit @('rev-parse','--verify','refs/stash') -AllowFailure -Quiet
    if ($result.ExitCode -ne 0 -or -not $result.Lines -or $result.Lines.Count -eq 0) { return $null }
    return (($result.Lines | Select-Object -Last 1) -as [string]).Trim()
}

Write-PrePullLine "DCOIR Safe Pre-Pull Apply"
Write-PrePullLine "Timestamp: $(Get-Date -Format o)"
Write-PrePullLine "Repo: $RepoRoot"
Write-PrePullLine ""

Write-PrePullLine "== BEFORE =="
Invoke-PrePullGit @('status','--short','--branch') -AllowFailure | Out-Null
Invoke-PrePullGit @('log','--oneline','-5') -AllowFailure | Out-Null

Write-PrePullLine ""
Write-PrePullLine "== STASH CURRENT WORK =="
$beforeStash = Get-StashHead
$stashResult = Invoke-PrePullGit @('stash','push','-u','-m',"$StashMessagePrefix-$stamp") -AllowFailure
$afterStash = Get-StashHead
$createdNewStash = $false
if ($afterStash -and $afterStash -ne $beforeStash) { $createdNewStash = $true }

if ($createdNewStash) {
    Write-PrePullLine "New stash commit: $afterStash"
} else {
    Write-PrePullLine "No new stash was created; no local work will be reapplied after pull."
}

Write-PrePullLine ""
Write-PrePullLine "== FETCH AND FAST-FORWARD PULL =="
Invoke-PrePullGit @('fetch',$Remote,'--prune') -AllowFailure | Out-Null
$pullResult = Invoke-PrePullGit @('pull','--ff-only',$Remote,$Branch) -AllowFailure

if ($pullResult.ExitCode -ne 0) {
    Write-PrePullLine ""
    Write-PrePullLine "PULL FAILED. Any newly-created stash was preserved. Do not continue manually."
    Invoke-PrePullGit @('status','--short','--branch') -AllowFailure | Out-Null
    Invoke-PrePullGit @('stash','list') -AllowFailure | Out-Null
    exit 1
}

if ($createdNewStash) {
    Write-PrePullLine ""
    Write-PrePullLine "== REAPPLY CAPTURED WORK =="
    $applyResult = Invoke-PrePullGit @('stash','apply',$afterStash) -AllowFailure
    if ($applyResult.ExitCode -ne 0) {
        Write-PrePullLine ""
        Write-PrePullLine "STASH APPLY HAD CONFLICTS. Stash was preserved. Do not commit yet."
        Invoke-PrePullGit @('status') -AllowFailure | Out-Null
        Invoke-PrePullGit @('diff','--name-only','--diff-filter=U') -AllowFailure | Out-Null
        Invoke-PrePullGit @('stash','list') -AllowFailure | Out-Null
        exit 2
    }
} else {
    Write-PrePullLine ""
    Write-PrePullLine "== REAPPLY CAPTURED WORK =="
    Write-PrePullLine "Skipped because no new stash was created."
}

Write-PrePullLine ""
Write-PrePullLine "== AFTER =="
Invoke-PrePullGit @('status','--short','--branch') -AllowFailure | Out-Null
Invoke-PrePullGit @('log','--oneline','-5') -AllowFailure | Out-Null

Write-PrePullLine ""
Write-PrePullLine "== STASH LIST =="
Invoke-PrePullGit @('stash','list') -AllowFailure | Out-Null

Write-PrePullLine ""
Write-PrePullLine "RESULT: If status shows only intended changes and no conflict files, review and commit in GitHub Desktop. Do not drop stashes until instructed."
Write-Host ""
Write-Host "Saved log to:"
Write-Host $log
