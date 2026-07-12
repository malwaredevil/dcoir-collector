Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirLoggingVersion = '2026-05-03.1'
$script:DcoirLoggingContext = @{}

function Get-DcoirLoggingVersion {
    [CmdletBinding()]
    param()
    return $script:DcoirLoggingVersion
}

function ConvertTo-DcoirLoggingSafeName {
    [CmdletBinding()]
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) { return 'tool' }
    $safe = (($Text -replace '[^A-Za-z0-9_.-]', '_').Trim('_'))
    if ([string]::IsNullOrWhiteSpace($safe)) { return 'tool' }
    return $safe
}

function New-DcoirToolLogPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$ToolName,
        [AllowNull()][string]$LogPath,
        [AllowNull()][string]$DownloadsDir
    )
    if (-not [string]::IsNullOrWhiteSpace($LogPath)) { return [System.IO.Path]::GetFullPath($LogPath) }
    if ([string]::IsNullOrWhiteSpace($DownloadsDir)) { $DownloadsDir = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR', 'Machine') }
    if ([string]::IsNullOrWhiteSpace($DownloadsDir)) {
        $profile = [Environment]::GetEnvironmentVariable('USERPROFILE', 'Process')
        if (-not [string]::IsNullOrWhiteSpace($profile)) { $DownloadsDir = Join-Path $profile 'Downloads' }
    }
    if ([string]::IsNullOrWhiteSpace($DownloadsDir)) { $DownloadsDir = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $DownloadsDir -PathType Container)) { New-Item -ItemType Directory -Force -Path $DownloadsDir | Out-Null }
    $safeTool = ConvertTo-DcoirLoggingSafeName -Text $ToolName
    return (Join-Path $DownloadsDir ('{0}_{1}.log.txt' -f $safeTool, (Get-Date -Format 'yyyyMMdd_HHmmss')))
}

function Initialize-DcoirToolLog {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$ToolName,
        [Parameter(Mandatory=$true)][string]$ToolVersion,
        [AllowNull()][string]$LogPath
    )
    $resolvedLog = New-DcoirToolLogPath -ToolName $ToolName -LogPath $LogPath
    $script:DcoirLoggingContext = @{
        ToolName = $ToolName
        ToolVersion = $ToolVersion
        LogPath = $resolvedLog
        StartedAt = (Get-Date -Format o)
        Phase = 'init'
    }
    Write-DcoirLogLine -Message ("Starting {0}." -f $ToolName)
    Write-DcoirLogLine -Message ("Tool version: {0}" -f $ToolVersion)
    Write-DcoirLogLine -Message ("Logging module version: {0}" -f $script:DcoirLoggingVersion)
    Write-DcoirLogLine -Message ("Log path: {0}" -f $resolvedLog)
    Write-DcoirLogLine -Message ("Current directory: {0}" -f (Get-Location).Path)
    return $resolvedLog
}

function Get-DcoirToolLogPath {
    [CmdletBinding()]
    param()
    return [string]$script:DcoirLoggingContext['LogPath']
}

function Set-DcoirLogPhase {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Phase)
    $script:DcoirLoggingContext['Phase'] = $Phase
    Write-DcoirLogLine -Message ("PHASE: {0}" -f $Phase)
}

function Write-DcoirLogLine {
    [CmdletBinding()]
    param([AllowNull()][string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), [string]$Message
    Write-Host $line
    $logPath = [string]$script:DcoirLoggingContext['LogPath']
    if (-not [string]::IsNullOrWhiteSpace($logPath)) {
        $parent = Split-Path -Parent $logPath
        if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        $enc = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::AppendAllText($logPath, $line + [Environment]::NewLine, $enc)
    }
}

function Write-DcoirLogObject {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [AllowNull()]$Object
    )
    Write-DcoirLogLine -Message ("{0}: {1}" -f $Label, ($Object | ConvertTo-Json -Depth 20 -Compress))
}

function Write-DcoirCaughtError {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]$ErrorRecord,
        [AllowNull()][string]$NextAction
    )
    $message = [string]$ErrorRecord.Exception.Message
    $type = [string]$ErrorRecord.Exception.GetType().FullName
    Write-DcoirLogLine -Message ("ERROR: {0}" -f $message)
    Write-DcoirLogLine -Message ("ERROR TYPE: {0}" -f $type)
    if ($ErrorRecord.ScriptStackTrace) { Write-DcoirLogLine -Message ("STACK: {0}" -f ([string]$ErrorRecord.ScriptStackTrace -replace "`r?`n", ' | ')) }
    if (-not [string]::IsNullOrWhiteSpace($NextAction)) { Write-DcoirLogLine -Message ("NEXT ACTION: {0}" -f $NextAction) }
    return [ordered]@{
        success = $false
        error_message = $message
        error_type = $type
        phase = [string]$script:DcoirLoggingContext['Phase']
        log_path = [string]$script:DcoirLoggingContext['LogPath']
        next_action = $NextAction
    }
}

Export-ModuleMember -Function Get-DcoirLoggingVersion,New-DcoirToolLogPath,Initialize-DcoirToolLog,Get-DcoirToolLogPath,Set-DcoirLogPhase,Write-DcoirLogLine,Write-DcoirLogObject,Write-DcoirCaughtError
