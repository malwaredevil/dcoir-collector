function New-DcoirActionsExecPowerShellWrapper {
    param(
        [Parameter(Mandatory=$true)][string]$CommandText,
        [string]$ExitCodePath = ''
    )

    $escapedExitCodePath = $ExitCodePath.Replace("'", "''")
    @"
`$dcoirExitCodePath = '$escapedExitCodePath'
`$ErrorActionPreference = 'Stop'
try {
    `$LASTEXITCODE = 0
    `$dcoirErrorCountBefore = `$Error.Count
$CommandText
    # Keep failure detection in the same PowerShell scope as the approved
    # command. Windows PowerShell 5.1 can still report process exit 0 after a
    # native nonzero result, so persist the resolved status before asking the
    # host to exit; the parent process reads this sidecar when available.
    `$dcoirCommandSucceeded = `$?
    `$dcoirNativeExitCode = `$LASTEXITCODE
    `$dcoirErrorCountAfter = `$Error.Count
    `$dcoirResolvedExitCode = 0
    if (`$null -ne `$dcoirNativeExitCode -and [int]`$dcoirNativeExitCode -ne 0) {
        `$dcoirResolvedExitCode = [int]`$dcoirNativeExitCode
    }
    elseif (`$dcoirErrorCountAfter -gt `$dcoirErrorCountBefore -or -not `$dcoirCommandSucceeded) {
        `$dcoirResolvedExitCode = 1
    }
    if (-not [string]::IsNullOrWhiteSpace(`$dcoirExitCodePath)) {
        [System.IO.File]::WriteAllText(`$dcoirExitCodePath, [string]`$dcoirResolvedExitCode)
    }
    exit `$dcoirResolvedExitCode
}
catch {
    if (-not [string]::IsNullOrWhiteSpace(`$dcoirExitCodePath)) {
        try { [System.IO.File]::WriteAllText(`$dcoirExitCodePath, '1') } catch { }
    }
    [Console]::Error.WriteLine((`$_ | Out-String))
    exit 1
}
"@
}

function Test-DcoirActionsExecPowerShellErrorRecord {
    param([AllowNull()][string]$StderrText)

    if ([string]::IsNullOrWhiteSpace($StderrText)) { return $false }
    return (
        $StderrText -match '(?m)^\s*\+\s*CategoryInfo\s*:' -and
        $StderrText -match '(?m)^\s*\+\s*FullyQualifiedErrorId\s*:'
    )
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
    $resolvedExitCodePath = Join-Path $RunRoot 'powershell.resolved_exit_code.txt'
    Remove-Item -LiteralPath $resolvedExitCodePath -Force -ErrorAction SilentlyContinue

    $started = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $timedOut = $false

    switch ($Shell) {
        'powershell_5' {
            # Windows PowerShell can emit a command error from a -File script yet
            # still return process exit code 0. The wrapper therefore persists a
            # resolved status sidecar when it reaches normal/catch resolution,
            # while the parent also retains the canonical PowerShell error-record
            # stderr guard for host-terminating failures that bypass the wrapper.
            (New-DcoirActionsExecPowerShellWrapper -CommandText $CommandText -ExitCodePath $resolvedExitCodePath) |
                Out-File -FilePath $commandPath -Encoding utf8
            $exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $commandPath)
        }
        'pwsh' {
            (New-DcoirActionsExecPowerShellWrapper -CommandText $CommandText -ExitCodePath $resolvedExitCodePath) |
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

    if (
        $exitCode -eq 0 -and
        $Shell -in @('powershell_5','pwsh') -and
        (Test-Path -LiteralPath $resolvedExitCodePath -PathType Leaf)
    ) {
        $resolvedText = (Get-Content -LiteralPath $resolvedExitCodePath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue).Trim()
        $resolvedExitCode = 0
        if ([int]::TryParse($resolvedText, [ref]$resolvedExitCode)) {
            $exitCode = $resolvedExitCode
        }
        else {
            $exitCode = 1
        }
    }

    if (
        $exitCode -eq 0 -and
        $Shell -in @('powershell_5','pwsh') -and
        (Test-Path -LiteralPath $stderrPath -PathType Leaf)
    ) {
        $stderrText = Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if (Test-DcoirActionsExecPowerShellErrorRecord -StderrText $stderrText) {
            $exitCode = 1
        }
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
