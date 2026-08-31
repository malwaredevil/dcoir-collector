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
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v37.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
)

$tests = @(
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v37_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_critic_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py'
)
foreach ($test in $tests) {
    Invoke-Native $python @($test)
}

Write-Host 'DCOIR v39 focused validation PASSED'
exit 0
