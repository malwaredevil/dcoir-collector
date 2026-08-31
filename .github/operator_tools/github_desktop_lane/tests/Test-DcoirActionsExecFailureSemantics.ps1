$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$modulePath = Join-Path $repoRoot '.github\operator_tools\github_desktop_lane\modules\Dcoir.ActionsExec\Dcoir.ActionsExec.psm1'
Import-Module $modulePath -Force

$tempRoot = Join-Path $env:TEMP ('dcoir-actions-exec-failure-semantics-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$fakeRepo = Join-Path $tempRoot 'repo'
$outputRoot = Join-Path $tempRoot 'out'
New-Item -ItemType Directory -Force -Path $fakeRepo, $outputRoot | Out-Null

function Invoke-Probe {
    param(
        [Parameter(Mandatory=$true)][string]$Id,
        [Parameter(Mandatory=$true)][string]$Command
    )

    $requestPath = Join-Path $tempRoot ($Id + '.json')
    [ordered]@{
        schema = 'dcoir.chatgpt_staging.exec_request.v1'
        request_id = $Id
        operator_approved = $true
        approved_at_utc = '2026-08-31T00:00:00Z'
        shell = 'powershell_5'
        timeout_seconds = 60
        artifact_retention_days = 1
        cleanup_request_after_run = $false
        approved_command_preview = "Failure semantics probe: $Id"
        command = $Command
    } | ConvertTo-Json -Depth 10 | Out-File -LiteralPath $requestPath -Encoding utf8

    return Invoke-DcoirActionsExecRequest `
        -RequestPath $requestPath `
        -RepoRoot $fakeRepo `
        -OutputRoot $outputRoot `
        -SecretEnvNames @()
}

try {
    $success = Invoke-Probe -Id 'success-probe' -Command "Write-Output 'ok'"
    if ($success.result -ne 'success' -or [int]$success.exit_code -ne 0) {
        throw "Expected success probe to return success/0; got $($success.result)/$($success.exit_code)"
    }

    $missing = Invoke-Probe -Id 'missing-command-probe' -Command "& 'Z:\\definitely-missing-dcoir-script.ps1'"
    if ($missing.result -ne 'failure' -or [int]$missing.exit_code -eq 0) {
        throw "Command-not-found was falsely green: $($missing.result)/$($missing.exit_code)"
    }
    $missingStderr = Get-Content -LiteralPath (Join-Path $missing.artifact_dir 'stderr.sanitized.txt') -Raw -ErrorAction Stop
    if ($missingStderr -notmatch 'not recognized|cannot find|does not exist') {
        throw 'Command-not-found probe did not preserve failure evidence in sanitized stderr.'
    }

    # A later successful statement must not heal an earlier command-resolution
    # failure into success/0.
    $healed = Invoke-Probe -Id 'healed-error-probe' -Command "& 'Z:\\definitely-missing-dcoir-script.ps1'`nWrite-Output 'continued-after-error'"
    if ($healed.result -ne 'failure' -or [int]$healed.exit_code -eq 0) {
        throw "Earlier PowerShell error was healed into false green: $($healed.result)/$($healed.exit_code)"
    }

    $throwing = Invoke-Probe -Id 'throw-probe' -Command "throw 'intentional exec failure probe'"
    if ($throwing.result -ne 'failure' -or [int]$throwing.exit_code -eq 0) {
        throw "PowerShell throw was falsely green: $($throwing.result)/$($throwing.exit_code)"
    }

    $native = Invoke-Probe -Id 'native-exit-probe' -Command "cmd /d /c exit 7"
    if ($native.result -ne 'failure' -or [int]$native.exit_code -ne 7) {
        throw "Native nonzero exit was not preserved: $($native.result)/$($native.exit_code)"
    }

    Write-Host 'Test-DcoirActionsExecFailureSemantics passed'
}
finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
