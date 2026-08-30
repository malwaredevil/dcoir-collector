$ErrorActionPreference = 'Continue'
Set-StrictMode -Version Latest

Set-Location $env:GITHUB_WORKSPACE

$script:Failures = @()

function Invoke-Recorded {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "=== $Label ==="
    $global:LASTEXITCODE = 0
    try {
        & $Command
        $code = [int]$LASTEXITCODE
    }
    catch {
        Write-Error $_
        $code = 1
    }
    if ($code -ne 0) {
        Write-Host "FAILED: $Label (exit $code)"
        $script:Failures += "$Label (exit $code)"
    }
    else {
        Write-Host "PASSED: $Label"
    }
}

$python = (Get-Command python -ErrorAction Stop).Source
$pythonTests = @(
    '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v19_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v20_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v21_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v22_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v23_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v24_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v25_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v26_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v28_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v29_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_quality_recovery_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_summary_problem_selftest.py',
    '.github/dcoir_review/scripts/validate-codeql-security-workflow.py'
)

Invoke-Recorded 'Compile v30 runtime and tests' {
    & $python -m py_compile `
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30.py' `
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py' `
        '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
}

foreach ($test in $pythonTests) {
    $currentTest = $test
    Invoke-Recorded "Python validation: $currentTest" { & $python $currentTest }
}

Invoke-Recorded 'Codex-local DCOIR validation smoke' {
    & bash '.github/dcoir_review/scripts/validate-codex-local.sh'
}

Invoke-Recorded 'PowerShell validation surface' {
    & pwsh -NoProfile -File '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowPowerShell7 -AllowEmpty
}

if ($script:Failures.Count -gt 0) {
    Write-Host '=== DCOIR v30 governed validation failures ==='
    foreach ($failure in $script:Failures) {
        Write-Host "- $failure"
    }
    throw ("DCOIR v30 governed validation failed: " + ($script:Failures -join '; '))
}

Write-Host 'DCOIR v30 governed validation completed successfully.'
exit 0
