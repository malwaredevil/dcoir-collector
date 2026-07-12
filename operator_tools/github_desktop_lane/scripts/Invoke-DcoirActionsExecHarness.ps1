[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [string]$RepoRoot = (Get-Location).Path,
    [string]$OutputRoot = (Join-Path $env:TEMP 'dcoir_chatgpt_exec'),
    [string]$JsonResultPath = '',
    [string]$GithubEnvPath = $env:GITHUB_ENV,
    [string[]]$SecretEnvNames = @('DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID')
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$modulePath = Join-Path $RepoRoot 'operator_tools\github_desktop_lane\modules\Dcoir.ActionsExec\Dcoir.ActionsExec.psm1'
Import-Module $modulePath -Force

function Write-GithubEnvValue {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($GithubEnvPath)) { return }
    "$Name=$Value" | Out-File -FilePath $GithubEnvPath -Encoding utf8 -Append
}

function Copy-DcoirExecArtifactReadback {
    param(
        [AllowNull()][string]$ArtifactDir,
        [AllowNull()][string]$ReportPath
    )
    if ([string]::IsNullOrWhiteSpace($ArtifactDir)) { return }
    if ([string]::IsNullOrWhiteSpace($ReportPath)) { return }
    if (-not (Test-Path -LiteralPath $ArtifactDir -PathType Container)) { return }
    $reportDir = Split-Path -Parent $ReportPath
    if ([string]::IsNullOrWhiteSpace($reportDir)) { return }
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    $readbackDir = Join-Path $reportDir 'artifact_readback'
    if (Test-Path -LiteralPath $readbackDir) {
        Remove-Item -LiteralPath $readbackDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $readbackDir | Out-Null
    Get-ChildItem -LiteralPath $ArtifactDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $readbackDir -Recurse -Force -ErrorAction Stop
    }
    @(
        '# ChatGPT artifact readback',
        '',
        'This directory is a sanitized unzipped copy of the GitHub Actions artifact contents.',
        '',
        'ChatGPT should read this repo path before asking the operator to download or upload ZIP artifacts.',
        '',
        'The GitHub Actions artifact is still uploaded separately for short-retention operator download and provenance.',
        ''
    ) | Out-File -FilePath (Join-Path $readbackDir 'README.md') -Encoding utf8
    if (Test-Path -LiteralPath $ReportPath -PathType Leaf) {
        @(
            '',
            '## Artifact readback',
            '',
            "- artifact_readback_path: $($readbackDir.Replace('\\','/'))",
            '- readback_contract: sanitized unzipped artifact files are committed as ordinary GitHub files for ChatGPT connector readback.',
            '- zip_artifact_contract: the GitHub Actions artifact remains available separately for short-retention operator download.'
        ) | Out-File -FilePath $ReportPath -Encoding utf8 -Append
    }
}

function Resolve-DcoirExecRequestPath {
    param([Parameter(Mandatory=$true)][string]$OriginalRequestPath)

    $raw = Get-Content -LiteralPath $OriginalRequestPath -Raw -Encoding UTF8
    $json = $raw | ConvertFrom-Json
    $hasCommand = ($json.PSObject.Properties.Name -contains 'command') -and -not [string]::IsNullOrWhiteSpace([string]$json.command)
    $hasScriptPath = ($json.PSObject.Properties.Name -contains 'script_path') -and -not [string]::IsNullOrWhiteSpace([string]$json.script_path)
    $needsSchema = (-not ($json.PSObject.Properties.Name -contains 'schema')) -or [string]::IsNullOrWhiteSpace([string]$json.schema)

    if ($needsSchema) {
        $json | Add-Member -NotePropertyName schema -NotePropertyValue 'dcoir.chatgpt_staging.exec_request.v1' -Force
    }

    $needsPatch = $needsSchema
    if (-not $hasCommand -and $hasScriptPath) {
        $scriptPath = [string]$json.script_path
        if ($scriptPath -notmatch '^chatgpt_staging/exec_scripts/[A-Za-z0-9._/-]+\.ps1$') {
            throw "script_path must point to chatgpt_staging/exec_scripts/<name>.ps1. Got: $scriptPath"
        }
        $fullScriptPath = Join-Path $RepoRoot ($scriptPath -replace '/', '\')
        if (-not (Test-Path -LiteralPath $fullScriptPath -PathType Leaf)) {
            throw "script_path file not found: $scriptPath"
        }

        $json | Add-Member -NotePropertyName command -NotePropertyValue ("& '" + $fullScriptPath.Replace("'", "''") + "'") -Force
        if (-not ($json.PSObject.Properties.Name -contains 'approved_command_preview') -or [string]::IsNullOrWhiteSpace([string]$json.approved_command_preview)) {
            $json | Add-Member -NotePropertyName approved_command_preview -NotePropertyValue "Run approved repo script: $scriptPath" -Force
        }
        $needsPatch = $true
    }

    if (-not $needsPatch) { return $OriginalRequestPath }

    $safeName = New-DcoirActionsExecSafeName -Value ([string]$json.request_id)
    $patchedDir = Join-Path $OutputRoot (Join-Path $safeName 'config')
    New-Item -ItemType Directory -Force -Path $patchedDir | Out-Null
    $patchedPath = Join-Path $patchedDir 'script_path_request.expanded.json'
    $json | ConvertTo-Json -Depth 20 | Out-File -FilePath $patchedPath -Encoding utf8
    return $patchedPath
}

try {
    $effectiveRequestPath = Resolve-DcoirExecRequestPath -OriginalRequestPath $RequestPath
    $result = Invoke-DcoirActionsExecRequest -RequestPath $effectiveRequestPath -RepoRoot $RepoRoot -OutputRoot $OutputRoot -SecretEnvNames $SecretEnvNames
    Copy-DcoirExecArtifactReadback -ArtifactDir ([string]$result.artifact_dir) -ReportPath ([string]$result.report_path)
    if ($JsonResultPath) { $result | ConvertTo-Json -Depth 8 | Out-File -FilePath $JsonResultPath -Encoding utf8 }
    Write-GithubEnvValue -Name 'DCOIR_EXEC_REQUEST_ID' -Value ([string]$result.request_id)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_RESULT' -Value ([string]$result.result)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_EXIT_CODE' -Value ([string]$result.exit_code)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_DIR' -Value ([string]$result.artifact_dir)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_NAME' -Value ([string]$result.artifact_name)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_RETENTION_DAYS' -Value ([string]$result.artifact_retention_days)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_REPORT_PATH' -Value ([string]$result.report_path)
    Write-GithubEnvValue -Name 'DCOIR_EXEC_CLEANUP_REQUEST_AFTER_RUN' -Value ([string]$result.cleanup_request_after_run)
    exit 0
}
catch {
    $safeId = 'harness-failure-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    try {
        if (Test-Path -LiteralPath $RequestPath -PathType Leaf) {
            $raw = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8
            $json = $raw | ConvertFrom-Json
            if ($json.request_id) { $safeId = New-DcoirActionsExecSafeName -Value ([string]$json.request_id) }
        }
    } catch { }

    $artifactDir = Join-Path (Join-Path $OutputRoot $safeId) 'artifact'
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
    $secretMap = Get-DcoirActionsExecSecretMap -SecretEnvNames $SecretEnvNames
    $errorText = ConvertTo-DcoirActionsExecSanitizedText -Text ($_ | Out-String) -SecretValuesByName $secretMap
    $errorText | Out-File -FilePath (Join-Path $artifactDir 'harness_error.sanitized.txt') -Encoding utf8

    $reportPath = Join-Path $RepoRoot (Join-Path 'chatgpt_staging/status_reports/chatgpt-exec' (Join-Path $safeId 'workflow_report.md'))
    Write-DcoirActionsExecReport -ReportPath $reportPath -RequestId $safeId -Result 'failure' -Shell 'unknown' -ExitCode 1 -TimedOut $false -CommandSha256 'unavailable' -ApprovedPreview 'Harness failed before approved command execution.' -CommandSanitized '[harness failed before command resolution]' -ErrorText $errorText -ArtifactRetentionDays 3
    Copy-DcoirExecArtifactReadback -ArtifactDir $artifactDir -ReportPath $reportPath

    if ($JsonResultPath) {
        [ordered]@{
            schema = 'dcoir.chatgpt_staging.exec_result.v1'
            request_id = $safeId
            result = 'failure'
            exit_code = 1
            timed_out = $false
            artifact_dir = $artifactDir
            artifact_name = "chatgpt-exec-$safeId"
            artifact_retention_days = 3
            cleanup_request_after_run = $false
            report_path = $reportPath
        } | ConvertTo-Json -Depth 8 | Out-File -FilePath $JsonResultPath -Encoding utf8
    }
    Write-GithubEnvValue -Name 'DCOIR_EXEC_REQUEST_ID' -Value $safeId
    Write-GithubEnvValue -Name 'DCOIR_EXEC_RESULT' -Value 'failure'
    Write-GithubEnvValue -Name 'DCOIR_EXEC_EXIT_CODE' -Value '1'
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_DIR' -Value $artifactDir
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_NAME' -Value "chatgpt-exec-$safeId"
    Write-GithubEnvValue -Name 'DCOIR_EXEC_ARTIFACT_RETENTION_DAYS' -Value '3'
    Write-GithubEnvValue -Name 'DCOIR_EXEC_REPORT_PATH' -Value $reportPath
    Write-GithubEnvValue -Name 'DCOIR_EXEC_CLEANUP_REQUEST_AFTER_RUN' -Value 'false'
    exit 0
}
