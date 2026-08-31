function New-DcoirActionsExecPowerShellWrapper {
    param([Parameter(Mandatory=$true)][string]$CommandText)

    @"
`$ErrorActionPreference = 'Stop'
try {
    `$global:LASTEXITCODE = 0
    & {
$CommandText
    }
    # Command resolution failures in Windows PowerShell may emit an error yet
    # neither enter catch nor set LASTEXITCODE. Capture `$? immediately before
    # any wrapper statement can overwrite it.
    `$dcoirCommandSucceeded = `$?
    `$dcoirNativeExitCode = `$global:LASTEXITCODE
    if (`$null -ne `$dcoirNativeExitCode -and [int]`$dcoirNativeExitCode -ne 0) {
        exit [int]`$dcoirNativeExitCode
    }
    if (-not `$dcoirCommandSucceeded) {
        exit 1
    }
    exit 0
}
catch {
    [Console]::Error.WriteLine((`$_ | Out-String))
    exit 1
}
"@
}

function Invoke-DcoirActionsExecProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Shell,
        [Parameter(Mandatory=$true)][string]$CommandText,
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$RunRoot,
        [int]$TimeoutSeconds = 1800
    )

    if ($TimeoutSeconds -lt 1) { $TimeoutSeconds = 1800 }
    $commandPath = Join-Path $RunRoot 'approved_command.ps1'
    $cmdPath = Join-Path $RunRoot 'approved_command.cmd'
    $stdoutPath = Join-Path $RunRoot 'stdout.raw.txt'
    $stderrPath = Join-Path $RunRoot 'stderr.raw.txt'

    $started = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $timedOut = $false

    switch ($Shell) {
        'powershell_5' {
            # Windows PowerShell can emit a command error from a -File script yet
            # still return process exit code 0 unless the script explicitly maps
            # PowerShell `$? and native LASTEXITCODE to a process exit status.
            (New-DcoirActionsExecPowerShellWrapper -CommandText $CommandText) |
                Out-File -FilePath $commandPath -Encoding utf8
            $exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $commandPath)
        }
        'pwsh' {
            (New-DcoirActionsExecPowerShellWrapper -CommandText $CommandText) |
                Out-File -FilePath $commandPath -Encoding utf8
            $exe = 'pwsh'
            $args = @('-NoProfile', '-File', $commandPath)
        }
        'cmd' {
            $CommandText | Out-File -FilePath $cmdPath -Encoding ascii
            $exe = Join-Path $env:SystemRoot 'System32\cmd.exe'
            $args = @('/d', '/s', '/c', $cmdPath)
        }
        default {
            throw "Unsupported shell '$Shell'. Supported values: powershell_5, pwsh, cmd."
        }
    }

    $p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -NoNewWindow -PassThru
    if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
        $timedOut = $true
        try { $p.Kill() } catch { }
        $exitCode = 124
    }
    else {
        $exitCode = [int]$p.ExitCode
    }

    $finished = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    return [pscustomobject]@{
        exit_code = $exitCode
        timed_out = $timedOut
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        command_path = $(if ($Shell -eq 'cmd') { $cmdPath } else { $commandPath })
        started_utc = $started
        finished_utc = $finished
    }
}

function Copy-DcoirActionsExecDownloads {
    param(
        [Parameter(Mandatory=$true)][string]$DownloadsDir,
        [Parameter(Mandatory=$true)][string]$ArtifactDir
    )
    if (-not (Test-Path -LiteralPath $DownloadsDir -PathType Container)) { return }
    $items = Get-ChildItem -LiteralPath $DownloadsDir -Force -ErrorAction SilentlyContinue
    if (-not $items) { return }
    $dest = Join-Path $ArtifactDir 'downloads'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
}
