[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestJson,
    [string]$RepoRoot = $env:DCOIR_REPO_ROOT,
    [string]$OutputDir = $env:DCOIR_DOWNLOADS_DIR,
    [string]$Remote = "origin",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$gitModule = Join-Path $PSScriptRoot '..\modules\Dcoir.Git\Dcoir.Git.psd1'
$snapshotModule = Join-Path $PSScriptRoot '..\modules\Dcoir.Snapshot\Dcoir.Snapshot.psd1'
Import-Module -Name (Resolve-Path -LiteralPath $gitModule).Path -Force -Global -ErrorAction Stop
Import-Module -Name (Resolve-Path -LiteralPath $snapshotModule).Path -Force -Global -ErrorAction Stop

$cmdGetEnv = Get-Command -Name 'Get-DcoirGitSystemEnvValue' -ErrorAction Stop
$cmdGit = Get-Command -Name 'Invoke-DcoirGitCommand' -ErrorAction Stop
$cmdAddLine = Get-Command -Name 'Add-DcoirSnapshotUtf8Line' -ErrorAction Stop
$cmdSafeName = Get-Command -Name 'ConvertTo-DcoirSnapshotSafeName' -ErrorAction Stop
$cmdCopyRepoPath = Get-Command -Name 'Copy-DcoirSnapshotRepoPath' -ErrorAction Stop

if (-not $RepoRoot) { $RepoRoot = & $cmdGetEnv -Name 'DCOIR_REPO_ROOT' -Required }
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw "Repo root not found: $RepoRoot" }
if (-not $OutputDir) { $OutputDir = & $cmdGetEnv -Name 'DCOIR_DOWNLOADS_DIR' -Required }
if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) { New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null }
if (-not (Test-Path -LiteralPath $ManifestJson)) { throw "Manifest not found: $ManifestJson" }

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$ManifestJson = (Resolve-Path -LiteralPath $ManifestJson).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$manifest = Get-Content -Raw -LiteralPath $ManifestJson | ConvertFrom-Json
$name = $manifest.name
$safeName = & $cmdSafeName -Name $name -Default 'targeted_snapshot'
$tmp = Join-Path $OutputDir "${safeName}_$stamp"
$stage = Join-Path $tmp "snapshot"
$zip = Join-Path $OutputDir "${safeName}_$stamp.zip"
$log = Join-Path $OutputDir "${safeName}_$stamp.log.txt"

function Write-Log {
    param([AllowEmptyString()][string]$Text)
    Write-Host $Text
    & $cmdAddLine -Path $log -Text $Text
}

function Invoke-TargetGit {
    param([Parameter(Mandatory = $true)][string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)
    return & $cmdGit -RepoRoot $RepoRoot -Arguments $Arguments -LogPath $log -AllowFailure:$AllowFailure -Quiet:$Quiet
}

try {
    if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
    Write-Log "DCOIR Targeted Snapshot Builder"
    Write-Log "Timestamp: $(Get-Date -Format o)"
    Write-Log "Repo: $RepoRoot"
    Write-Log "Manifest: $ManifestJson"

    Write-Log ""
    Write-Log "== BRANCH CHECK =="
    $branchOutput = @(Invoke-TargetGit @('branch', '--show-current'))
    $currentBranch = ($branchOutput.Lines | Select-Object -Last 1).Trim()
    Write-Log "Current branch: $currentBranch"
    if ($currentBranch -ne $Branch) { throw "Expected branch '$Branch' but found '$currentBranch'." }

    Write-Log ""
    Write-Log "== DIRTY TREE CHECK BEFORE PULL =="
    $dirtyResult = Invoke-TargetGit @('status', '--porcelain') -Quiet
    $dirty = @($dirtyResult.Lines)
    if ($dirty.Count -gt 0) {
        foreach ($line in $dirty) { Write-Log "DIRTY: $line" }
        throw "Working tree is not clean before snapshot. Commit, stash, or ask for recovery before continuing."
    }

    Write-Log ""
    Write-Log "== FETCH AND FAST-FORWARD PULL =="
    Invoke-TargetGit @('fetch', $Remote, '--prune') | Out-Null
    Invoke-TargetGit @('pull', '--ff-only', $Remote, $Branch) | Out-Null

    Write-Log ""
    Write-Log "== DIRTY TREE CHECK AFTER PULL =="
    $dirtyAfterResult = Invoke-TargetGit @('status', '--porcelain') -Quiet
    $dirtyAfter = @($dirtyAfterResult.Lines)
    if ($dirtyAfter.Count -gt 0) {
        foreach ($line in $dirtyAfter) { Write-Log "DIRTY: $line" }
        throw "Working tree is not clean after pull. Stop and upload log."
    }

    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    foreach ($rel in $manifest.paths) {
        if (-not $rel) { continue }
        & $cmdCopyRepoPath -RepoRoot $RepoRoot -StageRoot $stage -RelativePath ([string]$rel) -LogPath $log | Out-Null
    }
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    $friendlyZipScript = Join-Path $PSScriptRoot "New-DcoirChatGPTFriendlyZip.ps1"
    if (Test-Path -LiteralPath $friendlyZipScript -PathType Leaf) {
        . $friendlyZipScript
        New-DcoirChatGPTFriendlyZip -SourceFolder $stage -OutputZip $zip -IndexTitle "DCOIR targeted snapshot" -NormalizeTextEncoding | Out-Null
    } else {
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
    }
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue

    Write-Log ""
    Write-Log "== Snapshot complete =="
    Write-Log "ZIP: $zip"
    Write-Log "LOG: $log"
    Write-Host "Saved snapshot ZIP:"
    Write-Host $zip
    Write-Host "Saved log:"
    Write-Host $log
}
catch {
    Write-Log ""
    Write-Log "== Snapshot failed =="
    Write-Log $_.Exception.Message
    Write-Log "LOG: $log"
    throw
}
