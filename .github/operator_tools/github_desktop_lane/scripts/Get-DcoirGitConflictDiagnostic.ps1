[CmdletBinding()]
param(
    [string]$RepoRoot = $env:DCOIR_REPO_ROOT,
    [string]$OutputDir = $env:DCOIR_DOWNLOADS_DIR
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
$log = Join-Path $OutputDir "dcoir_git_conflict_diagnostic_$stamp.txt"

function Write-DiagLine {
    param([AllowEmptyString()][string]$Text)
    Write-Host $Text
    & $cmdAddLine -Path $log -Text $Text
}

function Invoke-DiagGit {
    param([Parameter(Mandatory=$true)][string[]]$Arguments, [switch]$AllowFailure)
    $result = & $cmdGit -RepoRoot $RepoRoot -Arguments $Arguments -LogPath $log -AllowFailure:$AllowFailure
    return $result
}

Write-DiagLine "DCOIR Git Conflict Diagnostic"
Write-DiagLine "Timestamp: $(Get-Date -Format o)"
Write-DiagLine "Repo: $RepoRoot"
Write-DiagLine ""
Write-DiagLine "== CURRENT DIRECTORY =="
Write-DiagLine (Get-Location).Path
Write-DiagLine ""
Write-DiagLine "== GIT VERSION =="
Invoke-DiagGit @('--version') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== BRANCH =="
Invoke-DiagGit @('branch','--show-current') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== HEAD =="
Invoke-DiagGit @('rev-parse','--short','HEAD') -AllowFailure | Out-Null
Invoke-DiagGit @('log','--oneline','-5') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== REMOTES =="
Invoke-DiagGit @('remote','-v') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== FETCH ORIGIN =="
Invoke-DiagGit @('fetch','origin','--prune') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== STATUS SHORT WITH BRANCH =="
Invoke-DiagGit @('status','--short','--branch') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== STATUS FULL =="
Invoke-DiagGit @('status') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== BRANCH VERBOSE =="
Invoke-DiagGit @('branch','-vv') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== AHEAD / BEHIND MAIN =="
$branchResult = & $cmdGit -RepoRoot $RepoRoot -Arguments @('branch','--show-current') -LogPath $null -AllowFailure -Quiet
$branch = (($branchResult.Lines | Select-Object -Last 1) -as [string]).Trim()
if ($branch) { Invoke-DiagGit @('rev-list','--left-right','--count',"$branch...origin/main") -AllowFailure | Out-Null }
Write-DiagLine ""
Write-DiagLine "== UNMERGED / CONFLICT FILES =="
Invoke-DiagGit @('diff','--name-only','--diff-filter=U') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== WORKING TREE DIFF SUMMARY =="
Invoke-DiagGit @('diff','--stat') -AllowFailure | Out-Null
Invoke-DiagGit @('diff','--name-status') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== STAGED DIFF SUMMARY =="
Invoke-DiagGit @('diff','--cached','--stat') -AllowFailure | Out-Null
Invoke-DiagGit @('diff','--cached','--name-status') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== UNTRACKED FILES =="
Invoke-DiagGit @('ls-files','--others','--exclude-standard') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== STASH LIST =="
Invoke-DiagGit @('stash','list') -AllowFailure | Out-Null
Write-DiagLine ""
Write-DiagLine "== REBASE / MERGE / CHERRY-PICK STATE =="
foreach ($statePath in @('.git/MERGE_HEAD','.git/rebase-merge','.git/rebase-apply','.git/CHERRY_PICK_HEAD')) {
    $full = Join-Path $RepoRoot $statePath
    if (Test-Path $full) { Write-DiagLine "$statePath exists" } else { Write-DiagLine "No $statePath" }
}
Write-DiagLine ""
Write-DiagLine "== RECENT ALL-BRANCH GRAPH =="
Invoke-DiagGit @('log','--oneline','--decorate','--graph','--all','-20') -AllowFailure | Out-Null
Write-Host ""
Write-Host "Saved diagnostic log to:"
Write-Host $log
