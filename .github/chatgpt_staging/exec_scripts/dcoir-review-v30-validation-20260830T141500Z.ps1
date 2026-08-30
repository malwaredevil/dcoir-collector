$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Set-Location $env:GITHUB_WORKSPACE

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "=== $Label ==="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
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

Invoke-Checked 'Compile v30 runtime and tests' {
    & $python -m py_compile `
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30.py' `
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py' `
        '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
}

foreach ($test in $pythonTests) {
    Invoke-Checked "Python validation: $test" { & $python $test }
}

Invoke-Checked 'Codex-local DCOIR validation smoke' {
    & bash '.github/dcoir_review/scripts/validate-codex-local.sh'
}

Invoke-Checked 'PowerShell validation surface' {
    & pwsh -NoProfile -File '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowPowerShell7 -AllowEmpty
}

Write-Host 'DCOIR v30 governed validation completed successfully.'
