$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $env:GITHUB_WORKSPACE

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    Write-Host ("> {0} {1}" -f $FilePath, ($ArgumentList -join ' '))
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed with exit code {0}: {1}" -f $LASTEXITCODE, $FilePath)
    }
}

$python = (Get-Command python -ErrorAction Stop).Source

Invoke-Native $python @(
    '-m', 'py_compile',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v37.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
)

Invoke-Native $python @('.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py')

$runtimeTests = Get-ChildItem '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v*_selftest.py' | Sort-Object Name
foreach ($test in $runtimeTests) {
    Invoke-Native $python @($test.FullName)
}

$tests = @(
    '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_quality_recovery_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_summary_problem_selftest.py'
)
foreach ($test in $tests) {
    Invoke-Native $python @($test)
}

Invoke-Native 'bash' @('.github/dcoir_review/scripts/validate-codex-local.sh')
Invoke-Native 'pwsh' @('-NoProfile', '-File', '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1', '-AllowPowerShell7', '-AllowEmpty')
Invoke-Native $python @('.github/dcoir_review/scripts/validate-codeql-security-workflow.py')

Write-Host 'DCOIR v39 full governed validation PASSED'
exit 0
