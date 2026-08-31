$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $env:GITHUB_WORKSPACE

$processSource = '.github/operator_tools/github_desktop_lane/modules/Dcoir.ActionsExec/Private/10-Process.ps1'
. (Resolve-Path $processSource)

$exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$diagRoot = Join-Path $env:RUNNER_TEMP ('dcoir-exit-diagnostic-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $diagRoot | Out-Null

function Invoke-ChildScript {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$ScriptText
    )
    $scriptPath = Join-Path $diagRoot ($Name + '.ps1')
    $stdoutPath = Join-Path $diagRoot ($Name + '.stdout.txt')
    $stderrPath = Join-Path $diagRoot ($Name + '.stderr.txt')
    $ScriptText | Out-File -LiteralPath $scriptPath -Encoding utf8
    $p = Start-Process -FilePath $exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$scriptPath) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -NoNewWindow -PassThru
    $p.WaitForExit()
    $stdout = if (Test-Path $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
    $stderr = if (Test-Path $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
    Write-Host "=== $Name ==="
    Write-Host "exit_code=$([int]$p.ExitCode)"
    Write-Host '--- stdout ---'
    Write-Host $stdout
    Write-Host '--- stderr ---'
    Write-Host $stderr
    return [int]$p.ExitCode
}

$missingCommand = "& 'Z:\\definitely-missing-dcoir-script.ps1'"
$wrapper = New-DcoirActionsExecPowerShellWrapper -CommandText $missingCommand
Write-Host '=== generated wrapper ==='
Write-Host $wrapper
$null = Invoke-ChildScript -Name 'generated-wrapper-missing' -ScriptText $wrapper

$directProbe = @'
$ErrorActionPreference = 'Stop'
$global:LASTEXITCODE = 0
$before = $Error.Count
& 'Z:\definitely-missing-dcoir-script.ps1'
$succeeded = $?
$last = $global:LASTEXITCODE
$after = $Error.Count
Write-Output "before=$before after=$after succeeded=$succeeded last=$last"
exit 0
'@
$null = Invoke-ChildScript -Name 'direct-same-scope-missing' -ScriptText $directProbe

$healedProbe = @'
$ErrorActionPreference = 'Continue'
$global:LASTEXITCODE = 0
$before = $Error.Count
& 'Z:\definitely-missing-dcoir-script.ps1'
Write-Output 'continued-after-error'
$succeeded = $?
$last = $global:LASTEXITCODE
$after = $Error.Count
Write-Output "before=$before after=$after succeeded=$succeeded last=$last"
exit 0
'@
$null = Invoke-ChildScript -Name 'direct-healed-missing' -ScriptText $healedProbe

Write-Host 'ChatGPT exec PowerShell exit diagnostic complete'
exit 0
