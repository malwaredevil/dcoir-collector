[CmdletBinding()]
param(
    [string]$RepoRoot = $env:DCOIR_REPO_ROOT,
    [string]$OutputDir = $env:DCOIR_DOWNLOADS_DIR,
    [string]$SnapshotName = "dcoir_text_only_repo_snapshot",
    [Int64]$MaxFileBytes = 5242880,
    [string[]]$ExcludeDirectoryNames = @(
        ".git", ".github-desktop", ".vs", ".vscode", "node_modules", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "env",
        "bin", "obj", "dist", "build", "target", ".terraform"
    ),
    [string[]]$ExcludeExtensions = @(
        ".7z", ".a", ".appx", ".bin", ".bmp", ".cab", ".class", ".dll", ".doc", ".docx",
        ".dylib", ".eot", ".exe", ".gif", ".gz", ".ico", ".iso", ".jar", ".jpeg", ".jpg",
        ".lib", ".mp3", ".mp4", ".msi", ".nupkg", ".otf", ".pdf", ".pdb", ".png", ".ppt",
        ".pptx", ".pyc", ".rar", ".so", ".tar", ".tgz", ".ttf", ".war", ".webp", ".woff",
        ".woff2", ".xls", ".xlsx", ".zip"
    ),
    [switch]$IncludeDotDirectories,
    [switch]$NoGitCleanCheck
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
$cmdScan = Get-Command -Name 'Get-DcoirTextSnapshotFiles' -ErrorAction Stop

if (-not $RepoRoot) { $RepoRoot = & $cmdGetEnv -Name 'DCOIR_REPO_ROOT' -Required }
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw "Repo root not found: $RepoRoot" }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $OutputDir) { $OutputDir = & $cmdGetEnv -Name 'DCOIR_DOWNLOADS_DIR' -Required }
if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) { New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null }
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$safeName = & $cmdSafeName -Name $SnapshotName -Default 'dcoir_text_only_repo_snapshot'
$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) "${safeName}_$stamp"
$stage = Join-Path $tmpRoot "snapshot"
$zipPath = Join-Path $OutputDir "${safeName}_$stamp.zip"
$logPath = Join-Path $OutputDir "${safeName}_$stamp.log.txt"
$manifestPath = Join-Path $OutputDir "${safeName}_$stamp.manifest.json"

function Write-Log {
    param([AllowEmptyString()][string]$Text)
    Write-Host $Text
    & $cmdAddLine -Path $logPath -Text $Text
}
function Invoke-SnapshotGit {
    param([Parameter(Mandatory=$true)][string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)
    return & $cmdGit -RepoRoot $RepoRoot -Arguments $Arguments -LogPath $logPath -AllowFailure:$AllowFailure -Quiet:$Quiet
}

try {
    Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    foreach ($path in @($zipPath, $logPath, $manifestPath)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }
    Write-Log "DCOIR Text-Only Repo Snapshot"
    Write-Log "Timestamp: $(Get-Date -Format o)"
    Write-Log "RepoRoot: $RepoRoot"
    Write-Log "OutputDir: $OutputDir"
    Write-Log "MaxFileBytes: $MaxFileBytes"
    Write-Log "Read-only: true"
    if (-not $NoGitCleanCheck) {
        Write-Log ""
        Write-Log "== GIT STATUS CHECK =="
        $statusResult = Invoke-SnapshotGit @('status','--porcelain') -AllowFailure -Quiet
        $statusLines = @($statusResult.Lines)
        if ($statusLines.Count -gt 0) {
            foreach ($line in $statusLines) { Write-Log "GIT-STATUS: $line" }
            Write-Log "Git status output is logged for context only. Snapshot will continue because this tool is read-only."
        } else { Write-Log "Git working tree appears clean." }
    }
    Write-Log ""
    Write-Log "== SCAN AND COPY TEXT FILES =="
    $scan = & $cmdScan -RepoRoot $RepoRoot -MaxFileBytes $MaxFileBytes -ExcludeDirectoryNames $ExcludeDirectoryNames -ExcludeExtensions $ExcludeExtensions -IncludeDotDirectories:$IncludeDotDirectories
    foreach ($skip in @($scan.Skipped)) { Write-Log "SKIP [$($skip.reason)]: $($skip.path)" }
    foreach ($item in @($scan.Included)) {
        $dest = Join-Path $stage $item.path
        $parent = Split-Path -Parent $dest
        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        Copy-Item -LiteralPath $item.full_name -Destination $dest -Force
        Write-Log "INCLUDE: $($item.path)"
    }
    $friendlyZipScript = Join-Path $PSScriptRoot "New-DcoirChatGPTFriendlyZip.ps1"
    if (Test-Path -LiteralPath $friendlyZipScript -PathType Leaf) {
        . $friendlyZipScript
        New-DcoirChatGPTFriendlyZip -SourceFolder $stage -OutputZip $zipPath -IndexTitle "DCOIR text-only repo snapshot" -NormalizeTextEncoding | Out-Null
    } else {
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -Force
    }
    $manifest = [ordered]@{
        tool = "New-DcoirTextOnlyRepoSnapshot.ps1"
        tool_version = "2026-05-01.3"
        created_at = (Get-Date -Format o)
        repo_root = $RepoRoot
        output_zip = $zipPath
        output_log = $logPath
        max_file_bytes = $MaxFileBytes
        include_dot_directories = [bool]$IncludeDotDirectories
        no_git_clean_check = [bool]$NoGitCleanCheck
        counts = [ordered]@{ included_files = @($scan.Included).Count; skipped_files = @($scan.Skipped).Count }
        included_files = @($scan.Included | Select-Object path,size_bytes,extension)
        skipped_files = @($scan.Skipped)
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Log ""
    Write-Log "== Snapshot complete =="
    Write-Log "Included files: $(@($scan.Included).Count)"
    Write-Log "Skipped files: $(@($scan.Skipped).Count)"
    Write-Log "ZIP: $zipPath"
    Write-Log "LOG: $logPath"
    Write-Log "MANIFEST: $manifestPath"
    Write-Host "Saved text-only snapshot ZIP:"
    Write-Host $zipPath
    Write-Host "Saved log:"
    Write-Host $logPath
    Write-Host "Saved manifest:"
    Write-Host $manifestPath
}
catch {
    Write-Log ""
    Write-Log "== Snapshot failed =="
    Write-Log $_.Exception.Message
    Write-Log "LOG: $logPath"
    throw
}
finally { Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue }
