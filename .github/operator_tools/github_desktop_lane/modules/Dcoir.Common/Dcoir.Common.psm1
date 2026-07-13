Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirCommonVersion = '2026-05-01.1'
$script:DcoirToolContext = $null

function Set-DcoirToolContext {
    [CmdletBinding()]
    param([AllowNull()]$Context)
    $script:DcoirToolContext = $Context
}

function Get-DcoirToolContext {
    [CmdletBinding()]
    param()
    return $script:DcoirToolContext
}

function Get-DcoirContextValue {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Name, $Default = $null)
    $ctx = Get-DcoirToolContext
    if ($null -eq $ctx) { return $Default }
    if ($ctx -is [System.Collections.IDictionary] -and $ctx.Contains($Name)) { return $ctx[$Name] }
    $prop = $ctx.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Set-DcoirContextValue {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Name, $Value)
    $ctx = Get-DcoirToolContext
    if ($null -eq $ctx) { return }
    if ($ctx -is [System.Collections.IDictionary]) { $ctx[$Name] = $Value; return }
    $ctx.$Name = $Value
}

function Test-DcoirPlaceholderPath {
    [CmdletBinding()]
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $v = $Value.Trim()
    return ($v -match '^[A-Za-z]:\\path\\to(\\|$)' -or $v -match '^/path/to(/|$)' -or $v -match 'your[_ -]?folder[_ -]?name[_ -]?here' -or $v -match 'your[_ -]?repo')
}

function Get-DcoirSystemEnvValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [switch]$Required,
        [AllowNull()][string]$Default
    )
    $machine = [Environment]::GetEnvironmentVariable($Name, 'Machine')
    if (Test-DcoirPlaceholderPath -Value $machine) {
        throw "$Name is set to a placeholder path in Machine/System environment scope: $machine"
    }
    if (-not [string]::IsNullOrWhiteSpace($machine)) { return $machine.Trim() }
    if (-not [string]::IsNullOrWhiteSpace($Default)) { return $Default }
    if ($Required) { throw "$Name is not set in Machine/System environment scope. Set it as a System environment variable, then open a new terminal." }
    return $null
}

function Resolve-DcoirPathText {
    [CmdletBinding()]
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) { return $null }
    $repoRoot = Get-DcoirSystemEnvValue -Name 'DCOIR_REPO_ROOT' -Required
    $downloads = Get-DcoirSystemEnvValue -Name 'DCOIR_DOWNLOADS_DIR' -Required
    $expanded = $Text.Replace('%DCOIR_REPO_ROOT%', $repoRoot).Replace('%DCOIR_DOWNLOADS_DIR%', $downloads).Replace('%USERPROFILE%', [string]$env:USERPROFILE)
    return [Environment]::ExpandEnvironmentVariables($expanded)
}

function ConvertTo-DcoirHashtable {
    [CmdletBinding()]
    param($InputObject)
    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $h = @{}
        foreach ($k in $InputObject.Keys) { $h[$k] = ConvertTo-DcoirHashtable -InputObject $InputObject[$k] }
        return $h
    }
    if ($InputObject -is [pscustomobject]) {
        $h = @{}
        foreach ($p in $InputObject.PSObject.Properties) { $h[$p.Name] = ConvertTo-DcoirHashtable -InputObject $p.Value }
        return $h
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $arr = @()
        foreach ($item in $InputObject) { $arr += ,(ConvertTo-DcoirHashtable -InputObject $item) }
        return $arr
    }
    return $InputObject
}

function Get-DcoirConfigValue {
    [CmdletBinding()]
    param($Map, [string]$Name, $Default = $null)
    if ($null -eq $Map) { return $Default }
    if ($Map -is [System.Collections.IDictionary] -and $Map.ContainsKey($Name)) { return $Map[$Name] }
    $prop = $Map.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function ConvertTo-DcoirSafeName {
    [CmdletBinding()]
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) { return '' }
    return (($Text -replace '[^A-Za-z0-9_.-]', '_').Trim('_'))
}

function Write-DcoirUtf8Text {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [AllowNull()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, [string]$Text, $enc)
}

function Add-DcoirUtf8Line {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [AllowNull()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($Path, ([string]$Text) + [Environment]::NewLine, $enc)
}

function Save-DcoirJson {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$Object)
    Write-DcoirUtf8Text -Path $Path -Text ($Object | ConvertTo-Json -Depth 40)
}

function Write-DcoirConsoleStep {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Write-DcoirStatus {
    [CmdletBinding()]
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    $logPath = [string](Get-DcoirContextValue -Name 'LogPath' -Default '')
    if (-not [string]::IsNullOrWhiteSpace($logPath)) { Add-DcoirUtf8Line -Path $logPath -Text $line }
}

function Write-DcoirPhase {
    [CmdletBinding()]
    param([string]$Name, [string]$Message)
    Set-DcoirContextValue -Name 'Phase' -Value $Name
    Write-DcoirStatus ("PHASE {0}: {1}" -f $Name, $Message)
}

function Format-DcoirInputMap {
    [CmdletBinding()]
    param($Map)
    if ($null -eq $Map) { return '(none)' }
    $pairs = @()
    foreach ($key in @($Map.Keys | Sort-Object)) { $pairs += ("{0}={1}" -f $key, [string]$Map[$key]) }
    if ($pairs.Count -eq 0) { return '(none)' }
    return ($pairs -join '; ')
}

Export-ModuleMember -Function Set-DcoirToolContext,Get-DcoirToolContext,Get-DcoirContextValue,Set-DcoirContextValue,Test-DcoirPlaceholderPath,Get-DcoirSystemEnvValue,Resolve-DcoirPathText,ConvertTo-DcoirHashtable,Get-DcoirConfigValue,ConvertTo-DcoirSafeName,Write-DcoirUtf8Text,Add-DcoirUtf8Line,Save-DcoirJson,Write-DcoirConsoleStep,Write-DcoirStatus,Write-DcoirPhase,Format-DcoirInputMap
