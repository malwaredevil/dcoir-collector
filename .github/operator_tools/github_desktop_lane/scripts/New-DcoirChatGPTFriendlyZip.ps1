[CmdletBinding()]
param(
    [string]$SourceFolder,
    [string]$OutputZip,
    [string]$IndexTitle = "DCOIR ChatGPT-friendly upload package",
    [string[]]$SkipDirectoryNames = @(".git", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "env", "dist", "build", "target", "__MACOSX"),
    [string[]]$SkipFileNames = @(".DS_Store", "Thumbs.db", "Desktop.ini"),
    [int]$MaxArchivePathLength = 180,
    [switch]$NormalizeTextEncoding,
    [switch]$NoIndex
)

$ErrorActionPreference = "Stop"
$Script:DcoirChatGPTFriendlyZipVersion = "2026-05-03.1"

function Get-DcoirFileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }

    $getFileHash = Get-Command -Name Get-FileHash -ErrorAction SilentlyContinue
    if ($getFileHash) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    }

    $stream = [System.IO.File]::OpenRead($Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($stream)
        return ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Get-DcoirRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes source root: $Path" }
    return ConvertTo-DcoirArchivePath -PathText ($pathFull.Substring($rootFull.Length))
}

function ConvertTo-DcoirArchivePath {
    param([Parameter(Mandatory = $true)][string]$PathText)
    $normalized = $PathText -replace '\\', '/'
    while ($normalized.Contains('//')) { $normalized = $normalized.Replace('//', '/') }
    $normalized = $normalized.TrimStart('/')
    if ($normalized -match '(^|/)\.\.(/|$)') { throw "Unsafe archive path contains parent traversal: $PathText" }
    if ($normalized -match '^[A-Za-z]:') { throw "Unsafe archive path is drive-qualified: $PathText" }
    if ([string]::IsNullOrWhiteSpace($normalized)) { throw "Archive path resolved to empty string." }
    return $normalized
}

function Get-DcoirEncodingGuess {
    param([Parameter(Mandatory = $true)][string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { return "utf-8-bom" }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) { return "utf-16le" }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) { return "utf-16be" }
    $limit = [Math]::Min($bytes.Length, 8192)
    for ($i = 0; $i -lt $limit; $i++) { if ($bytes[$i] -eq 0) { return "binary-or-utf16-no-bom" } }
    return "utf-8-or-ascii"
}

function Test-DcoirHiddenOrSystemPath {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$File,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [string[]]$DirectoryNames,
        [string[]]$FileNames
    )
    if (($File.Attributes -band [System.IO.FileAttributes]::Hidden) -or ($File.Attributes -band [System.IO.FileAttributes]::System)) { return $true }
    if ($FileNames -contains $File.Name) { return $true }
    if ($File.Name.StartsWith('.')) { return $true }
    foreach ($part in ($RelativePath -split '/')) {
        if ($DirectoryNames -contains $part) { return $true }
        if ($part -eq "__MACOSX") { return $true }
    }
    return $false
}

function Copy-DcoirFriendlyFile {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [switch]$NormalizeTextEncoding
    )
    $parent = Split-Path -Parent $DestinationPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $guess = Get-DcoirEncodingGuess -Path $SourcePath
    $textExts = @(".txt", ".md", ".json", ".csv", ".log", ".ps1", ".psm1", ".psd1", ".yml", ".yaml", ".xml")
    $ext = [System.IO.Path]::GetExtension($SourcePath).ToLowerInvariant()
    if ($NormalizeTextEncoding -and ($textExts -contains $ext) -and ($guess -eq "utf-16le" -or $guess -eq "utf-16be" -or $guess -eq "utf-8-bom")) {
        $text = [System.IO.File]::ReadAllText($SourcePath)
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($DestinationPath, $text, $utf8NoBom)
        return "normalized:$guess-to-utf8"
    }
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    return "copied:$guess"
}

function Add-DcoirZipEntry {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ArchivePath
    )
    $entryName = ConvertTo-DcoirArchivePath -PathText $ArchivePath
    if ($entryName.Contains('\')) { throw "Archive entry contains backslash after normalization: $entryName" }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($Archive, $FilePath, $entryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
}

function New-DcoirRootlessZip {
    param(
        [Parameter(Mandatory = $true)][string]$StageFolder,
        [Parameter(Mandatory = $true)][string]$OutputZip,
        [string[]]$PriorityEntries = @("diagnostic_index.md", "captured_files.json", "zip_manifest.json")
    )
    if (Test-Path -LiteralPath $OutputZip) { Remove-Item -LiteralPath $OutputZip -Force }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $stream = [System.IO.File]::Open($OutputZip, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        $added = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $PriorityEntries) {
            $candidate = Join-Path $StageFolder ($entry -replace '/', [System.IO.Path]::DirectorySeparatorChar)
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $archivePath = ConvertTo-DcoirArchivePath -PathText $entry
                Add-DcoirZipEntry -Archive $archive -FilePath $candidate -ArchivePath $archivePath
                [void]$added.Add($archivePath)
            }
        }
        foreach ($file in @(Get-ChildItem -LiteralPath $StageFolder -Recurse -File -Force | Sort-Object FullName)) {
            $rel = Get-DcoirRelativePath -Root $StageFolder -Path $file.FullName
            if ($added.Contains($rel)) { continue }
            Add-DcoirZipEntry -Archive $archive -FilePath $file.FullName -ArchivePath $rel
            [void]$added.Add($rel)
        }
    }
    finally {
        $archive.Dispose()
        $stream.Dispose()
    }
}

function New-DcoirChatGPTFriendlyZip {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$SourceFolder,
        [Parameter(Mandatory = $true)][string]$OutputZip,
        [string]$IndexTitle = "DCOIR ChatGPT-friendly upload package",
        [string[]]$SkipDirectoryNames = @(".git", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "env", "dist", "build", "target", "__MACOSX"),
        [string[]]$SkipFileNames = @(".DS_Store", "Thumbs.db", "Desktop.ini"),
        [int]$MaxArchivePathLength = 180,
        [switch]$NormalizeTextEncoding,
        [switch]$NoIndex
    )
    if (-not (Test-Path -LiteralPath $SourceFolder -PathType Container)) { throw "SourceFolder not found: $SourceFolder" }
    $source = (Resolve-Path -LiteralPath $SourceFolder).Path
    $outputParent = Split-Path -Parent $OutputZip
    if (-not $outputParent) { $outputParent = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) { New-Item -ItemType Directory -Force -Path $outputParent | Out-Null }
    $output = [System.IO.Path]::GetFullPath($OutputZip)
    $stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("dcoir_chatgpt_zip_" + [System.Guid]::NewGuid().ToString("N"))
    $stage = Join-Path $stageRoot "payload"
    $captured = New-Object System.Collections.Generic.List[object]
    $skipped = New-Object System.Collections.Generic.List[object]
    try {
        New-Item -ItemType Directory -Force -Path $stage | Out-Null
        foreach ($file in @(Get-ChildItem -LiteralPath $source -Recurse -File -Force | Sort-Object FullName)) {
            $rel = Get-DcoirRelativePath -Root $source -Path $file.FullName
            if ($rel.Length -gt $MaxArchivePathLength) {
                $skipped.Add([pscustomobject]@{ path = $rel; reason = "archive_path_too_long"; size_bytes = $file.Length }) | Out-Null
                continue
            }
            if (Test-DcoirHiddenOrSystemPath -File $file -RelativePath $rel -DirectoryNames $SkipDirectoryNames -FileNames $SkipFileNames) {
                $skipped.Add([pscustomobject]@{ path = $rel; reason = "hidden_or_system_metadata"; size_bytes = $file.Length }) | Out-Null
                continue
            }
            $dest = Join-Path $stage ($rel -replace '/', [System.IO.Path]::DirectorySeparatorChar)
            $copyMode = Copy-DcoirFriendlyFile -SourcePath $file.FullName -DestinationPath $dest -NormalizeTextEncoding:$NormalizeTextEncoding
            $captured.Add([pscustomobject]@{
                path = $rel
                size_bytes = $file.Length
                sha256 = Get-DcoirFileSha256 -Path $file.FullName
                encoding_guess = Get-DcoirEncodingGuess -Path $file.FullName
                copy_mode = $copyMode
            }) | Out-Null
        }
        $createdAt = Get-Date -Format o
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $capturedJson = [ordered]@{
            tool = "New-DcoirChatGPTFriendlyZip.ps1"
            tool_version = $Script:DcoirChatGPTFriendlyZipVersion
            created_at = $createdAt
            source_folder = $source
            output_zip = $output
            normalize_text_encoding = [bool]$NormalizeTextEncoding
            optimized_for_chatgpt_unpacking = $true
            rootless = $true
            archive_path_separator = "/"
            priority_entries_first = @("diagnostic_index.md", "captured_files.json", "zip_manifest.json")
            captured_count = $captured.Count
            skipped_count = $skipped.Count
            captured_files = @($captured.ToArray())
            skipped_files = @($skipped.ToArray())
        }
        [System.IO.File]::WriteAllText((Join-Path $stage "captured_files.json"), ($capturedJson | ConvertTo-Json -Depth 8), $utf8NoBom)
        if (-not $NoIndex) {
            $index = @(
                "# $IndexTitle", "", "Created: $createdAt", "Tool: New-DcoirChatGPTFriendlyZip.ps1 $Script:DcoirChatGPTFriendlyZipVersion",
                "Source folder: $source", "Captured files: $($captured.Count)", "Skipped files: $($skipped.Count)",
                "Normalize text encoding: $([bool]$NormalizeTextEncoding)", "Archive path separator: /", "Rootless ZIP: true", "", "## Fast triage files", "- diagnostic_index.md", "- captured_files.json", "- zip_manifest.json", "", "## Captured payload", "See captured_files.json for file list, sizes, hashes, and encoding guesses."
            )
            [System.IO.File]::WriteAllText((Join-Path $stage "diagnostic_index.md"), ($index -join "`n"), $utf8NoBom)
        }
        $entries = @($captured.ToArray() | ForEach-Object { $_.path }) + @("captured_files.json", "zip_manifest.json")
        if (-not $NoIndex) { $entries += "diagnostic_index.md" }
        $zipManifest = [ordered]@{
            tool = "New-DcoirChatGPTFriendlyZip.ps1"
            tool_version = $Script:DcoirChatGPTFriendlyZipVersion
            created_at = $createdAt
            output_zip = $output
            rootless = $true
            optimized_for_chatgpt_unpacking = $true
            archive_path_separator = "/"
            hidden_system_files_skipped = $true
            max_archive_path_length = $MaxArchivePathLength
            priority_entries_first = @("diagnostic_index.md", "captured_files.json", "zip_manifest.json")
            entries = @($entries | ForEach-Object { ConvertTo-DcoirArchivePath -PathText $_ })
        }
        [System.IO.File]::WriteAllText((Join-Path $stage "zip_manifest.json"), ($zipManifest | ConvertTo-Json -Depth 8), $utf8NoBom)
        New-DcoirRootlessZip -StageFolder $stage -OutputZip $output
        return [pscustomobject]@{
            output_zip = $output
            source_folder = $source
            captured_count = $captured.Count
            skipped_count = $skipped.Count
            normalize_text_encoding = [bool]$NormalizeTextEncoding
            optimized_for_chatgpt_unpacking = $true
            archive_path_separator = "/"
        }
    }
    finally {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($PSBoundParameters.ContainsKey('SourceFolder') -or $PSBoundParameters.ContainsKey('OutputZip')) {
    if (-not $SourceFolder -or -not $OutputZip) { throw "When running this script directly, provide both -SourceFolder and -OutputZip." }
    $result = New-DcoirChatGPTFriendlyZip @PSBoundParameters
    $result | ConvertTo-Json -Depth 5
}
