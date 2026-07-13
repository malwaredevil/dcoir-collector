Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirRepoPatchVersion = '2026-05-01.2'

function Add-DcoirRepoPatchUtf8Line {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [AllowEmptyString()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($Path, ([string]$Text) + [Environment]::NewLine, $enc)
}

function Test-DcoirRepoPatchRelativePathSafe {
    [CmdletBinding()]
    param([AllowNull()][string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) { return $false }
    if ($RelativePath -match '^[A-Za-z]:') { return $false }
    if ($RelativePath.StartsWith('\\')) { return $false }
    if ($RelativePath.StartsWith('/')) { return $false }
    if ($RelativePath -match '(^|[\\/])\.\.([\\/]|$)') { return $false }
    return $true
}

function ConvertTo-DcoirRepoPatchRelativePath {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RelativePath)
    if (-not (Test-DcoirRepoPatchRelativePathSafe -RelativePath $RelativePath)) { throw "Unsafe relative path: $RelativePath" }
    return ($RelativePath -replace '\\', '/').TrimStart('/')
}

function Get-DcoirRepoPatchTrimmedRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Root)
    $trimChars = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    return ([System.IO.Path]::GetFullPath($Root)).TrimEnd($trimChars)
}

function Resolve-DcoirRepoPatchUnderRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Root, [Parameter(Mandatory=$true)][string]$RelativePath)
    $rel = ConvertTo-DcoirRepoPatchRelativePath -RelativePath $RelativePath
    $candidate = Join-Path $Root ($rel -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    $rootFull = (Get-DcoirRepoPatchTrimmedRoot -Root $Root) + [System.IO.Path]::DirectorySeparatorChar
    $candidateFull = [System.IO.Path]::GetFullPath($candidate)
    if (-not $candidateFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes root: $RelativePath" }
    return $candidateFull
}

function Get-DcoirRepoPatchFileSha256 {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $sha = Get-FileHash -Algorithm SHA256 -LiteralPath $Path
    return $sha.Hash.ToLowerInvariant()
}

function Test-DcoirRepoPatchAllowedTargetRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RelativePath, [Parameter(Mandatory=$true)][object[]]$AllowedRoots)
    if (-not $AllowedRoots -or $AllowedRoots.Count -eq 0) { throw 'Manifest must define allowed_target_roots.' }
    $rel = (ConvertTo-DcoirRepoPatchRelativePath -RelativePath $RelativePath).ToLowerInvariant()
    foreach ($root in $AllowedRoots) {
        if (-not $root) { continue }
        $r = (ConvertTo-DcoirRepoPatchRelativePath -RelativePath ([string]$root)).ToLowerInvariant().TrimEnd('/')
        if ($rel -eq $r -or $rel.StartsWith($r + '/')) { return $true }
    }
    return $false
}

function Find-DcoirRepoPatchPayloadBase {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$BaseRoot, [AllowNull()][object[]]$CopyMap, [AllowNull()][string]$Policy)
    $policyValue = 'auto'
    if ($Policy) { $policyValue = ([string]$Policy).ToLowerInvariant() }
    if ($policyValue -eq 'none') { return $BaseRoot }
    if ($policyValue -ne 'auto' -and $policyValue -ne 'single-child') { throw "Unsupported payload_root_policy: $Policy" }
    $roots = New-Object System.Collections.Generic.List[string]
    $roots.Add($BaseRoot) | Out-Null
    $children = @(Get-ChildItem -LiteralPath $BaseRoot -Directory -Force -ErrorAction SilentlyContinue)
    if ($children.Count -eq 1) { $roots.Add($children[0].FullName) | Out-Null }
    foreach ($root in $roots) {
        $allFound = $true
        foreach ($item in @($CopyMap)) {
            $sourcePath = [string]$item.source
            if (-not $sourcePath) { continue }
            $candidate = Resolve-DcoirRepoPatchUnderRoot -Root $root -RelativePath $sourcePath
            if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { $allFound = $false; break }
        }
        if ($allFound) { return $root }
    }
    if ($policyValue -eq 'single-child' -and $children.Count -eq 1) { return $children[0].FullName }
    return $BaseRoot
}

Export-ModuleMember -Function Add-DcoirRepoPatchUtf8Line,Test-DcoirRepoPatchRelativePathSafe,ConvertTo-DcoirRepoPatchRelativePath,Get-DcoirRepoPatchTrimmedRoot,Resolve-DcoirRepoPatchUnderRoot,Get-DcoirRepoPatchFileSha256,Test-DcoirRepoPatchAllowedTargetRoot,Find-DcoirRepoPatchPayloadBase
