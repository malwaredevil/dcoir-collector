Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirSnapshotVersion = '2026-05-01.2'

function Add-DcoirSnapshotUtf8Line {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [AllowEmptyString()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($Path, ([string]$Text) + [Environment]::NewLine, $enc)
}

function ConvertTo-DcoirSnapshotSafeName {
    [CmdletBinding()]
    param([AllowNull()][string]$Name, [string]$Default = 'snapshot')
    if ([string]::IsNullOrWhiteSpace($Name)) { $Name = $Default }
    $safe = ($Name -replace '[^A-Za-z0-9_.-]', '_').Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) { return $Default }
    return $safe
}

function Get-DcoirSnapshotTrimmedRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Root)
    $trimChars = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    return ([System.IO.Path]::GetFullPath($Root)).TrimEnd($trimChars)
}

function Assert-DcoirRepoRelativePath {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) { throw 'Repo-relative path is empty.' }
    if ([System.IO.Path]::IsPathRooted($RelativePath) -or $RelativePath -match '^[A-Za-z]:') { throw "Absolute path is not allowed: $RelativePath" }
    if ($RelativePath -match '(^|[\\/])\.\.([\\/]|$)' -or $RelativePath -eq '..') { throw "Parent path segment is not allowed: $RelativePath" }
    return $RelativePath
}

function Test-DcoirPathUnderRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)][string]$Root)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = (Get-DcoirSnapshotTrimmedRoot -Root $Root) + [System.IO.Path]::DirectorySeparatorChar
    return $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-DcoirRepoRelativePath {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)][string]$RepoRoot)
    $trimmedRoot = Get-DcoirSnapshotTrimmedRoot -Root $RepoRoot
    $repoUri = [System.Uri]::new(($trimmedRoot + [System.IO.Path]::DirectorySeparatorChar))
    $fileUri = [System.Uri]::new($Path)
    return [System.Uri]::UnescapeDataString($repoUri.MakeRelativeUri($fileUri).ToString()).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function Test-DcoirLikelyBinaryFile {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path)
    $bufferSize = 8192
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $length = [Math]::Min($bufferSize, [int]$stream.Length)
        if ($length -le 0) { return $false }
        $buffer = New-Object byte[] $length
        [void]$stream.Read($buffer, 0, $length)
        for ($i = 0; $i -lt $length; $i++) { if ($buffer[$i] -eq 0) { return $true } }
        return $false
    }
    finally { $stream.Dispose() }
}

function Copy-DcoirSnapshotRepoPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [Parameter(Mandatory=$true)][string]$StageRoot,
        [Parameter(Mandatory=$true)][string]$RelativePath,
        [AllowNull()][string]$LogPath
    )
    $rel = Assert-DcoirRepoRelativePath -RelativePath $RelativePath
    $src = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $src)) { throw "Requested path is missing: $rel" }
    $dst = Join-Path $StageRoot $rel
    $parent = Split-Path -Parent $dst
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    if (Test-Path -LiteralPath $src -PathType Container) {
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -LiteralPath $src -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dst -Recurse -Force }
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
    if (-not [string]::IsNullOrWhiteSpace($LogPath)) { Add-DcoirSnapshotUtf8Line -Path $LogPath -Text "COPIED: $rel" }
    return $rel
}

function Get-DcoirTextSnapshotFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [Int64]$MaxFileBytes = 5242880,
        [string[]]$ExcludeDirectoryNames,
        [string[]]$ExcludeExtensions,
        [switch]$IncludeDotDirectories
    )
    $included = New-Object System.Collections.Generic.List[object]
    $skipped = New-Object System.Collections.Generic.List[object]
    $allFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -Force -File
    foreach ($file in $allFiles) {
        $full = $file.FullName
        if (-not (Test-DcoirPathUnderRoot -Path $full -Root $RepoRoot)) { $skipped.Add([pscustomobject]@{ path = $full; reason = 'outside_repo_root'; size_bytes = $file.Length }) | Out-Null; continue }
        $rel = Get-DcoirRepoRelativePath -Path $full -RepoRoot $RepoRoot
        $parts = $rel -split '[\\/]'
        $dirParts = if ($parts.Count -gt 1) { $parts[0..($parts.Count - 2)] } else { @() }
        $excludedDir = $null
        foreach ($part in $dirParts) {
            if ($ExcludeDirectoryNames -contains $part) { $excludedDir = $part; break }
            if (-not $IncludeDotDirectories -and $part.StartsWith('.') -and $part -ne '.github') { $excludedDir = $part; break }
        }
        if ($excludedDir) { $skipped.Add([pscustomobject]@{ path = $rel; reason = "excluded_directory:$excludedDir"; size_bytes = $file.Length }) | Out-Null; continue }
        $ext = $file.Extension.ToLowerInvariant()
        if ($ExcludeExtensions -contains $ext) { $skipped.Add([pscustomobject]@{ path = $rel; reason = "excluded_extension:$ext"; size_bytes = $file.Length }) | Out-Null; continue }
        if ($file.Length -gt $MaxFileBytes) { $skipped.Add([pscustomobject]@{ path = $rel; reason = 'over_max_file_bytes'; size_bytes = $file.Length }) | Out-Null; continue }
        if (Test-DcoirLikelyBinaryFile -Path $full) { $skipped.Add([pscustomobject]@{ path = $rel; reason = 'binary_sniff'; size_bytes = $file.Length }) | Out-Null; continue }
        $included.Add([pscustomobject]@{ full_name = $full; path = $rel; size_bytes = $file.Length; extension = $ext }) | Out-Null
    }
    return [pscustomobject]@{ Included = @($included.ToArray()); Skipped = @($skipped.ToArray()) }
}

Export-ModuleMember -Function Add-DcoirSnapshotUtf8Line,ConvertTo-DcoirSnapshotSafeName,Get-DcoirSnapshotTrimmedRoot,Assert-DcoirRepoRelativePath,Test-DcoirPathUnderRoot,Get-DcoirRepoRelativePath,Test-DcoirLikelyBinaryFile,Copy-DcoirSnapshotRepoPath,Get-DcoirTextSnapshotFiles
