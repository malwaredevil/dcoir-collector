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
    '.github/dcoir_review/scripts/dcoir_review/pareto_context/part_05a_hybrid_review.py',
    '.github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
)

$tests = @(
    '.github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py'
)
foreach ($test in $tests) {
    Invoke-Native $python @($test)
}

$configText = Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml' -Raw
if ($configText -notmatch '(?m)^debug:\s*false\s*$') { throw 'Production debug must remain false.' }
if ($configText -notmatch '(?m)^per_file_review_concurrency:\s*4\s*$') { throw 'v40 governed primary concurrency is not 4.' }
if ($configText -notmatch '(?m)^script_timeout_seconds:\s*2400\s*$') { throw 'v40 internal timeout is not 2400 seconds.' }
if ($configText -notmatch 'dcoir_review_per_file_coverage_recovery_v40_selftest\.py') { throw 'v40 selftest is missing from governed validation commands.' }

$workflowText = Get-Content -LiteralPath '.github/workflows/reusable-openrouter-pr-review.yml' -Raw
if ($workflowText -notmatch '(?m)^\s*timeout-minutes:\s*45\s*$') { throw 'v40 reusable review workflow timeout is not 45 minutes.' }

Write-Host 'DCOIR v40 focused validation PASSED'
exit 0
