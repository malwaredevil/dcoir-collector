[CmdletBinding()]
param(
    [string[]]$Path,
    [switch]$AllowPowerShell7,
    [switch]$AllowEmpty
)

$ErrorActionPreference = 'Stop'

$version = $PSVersionTable.PSVersion
$edition = $PSVersionTable.PSEdition
Write-Host "PowerShell version: $version"
Write-Host "PowerShell edition: $edition"

if (-not $AllowPowerShell7) {
    if ($version.Major -ne 5 -or $version.Minor -ne 1) {
        throw "Expected Windows PowerShell 5.1. Use -AllowPowerShell7 only for local syntax checks outside the Windows PowerShell 5.1 workflow. Found $version."
    }
    if ($edition -and $edition -ne 'Desktop') {
        throw "Expected Windows PowerShell Desktop edition. Found $edition."
    }
}

function Get-TrackedPowerShellFiles {
    if ($Path -and $Path.Count -gt 0) {
        return @($Path | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $files = @(git ls-files '*.ps1' '*.psm1' '*.psd1' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $files.Count -gt 0) {
            return @($files | Where-Object { Test-Path -LiteralPath $_ })
        }
    }

    return @(Get-ChildItem -LiteralPath . -Recurse -File -Include '*.ps1','*.psm1','*.psd1' |
        Where-Object { $_.FullName -notmatch '\\.git\\' } |
        ForEach-Object { $_.FullName })
}

$files = @(Get-TrackedPowerShellFiles | Sort-Object -Unique)

if (-not $files -or $files.Count -eq 0) {
    if ($AllowEmpty) {
        Write-Host 'No PowerShell files found.'
        exit 0
    }
    throw 'No PowerShell files found for Windows PowerShell 5.1 validation.'
}

Write-Host "Validating $($files.Count) PowerShell file(s)."
$failures = New-Object System.Collections.Generic.List[string]

foreach ($file in $files) {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors -and $parseErrors.Count -gt 0) {
        $messages = ($parseErrors | ForEach-Object { $_.Message }) -join ' | '
        $failures.Add("${file}: $messages")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Windows PowerShell parser validation failed for $($failures.Count) file(s)."
}

Write-Host 'PASS: PowerShell parser validation completed successfully.'
