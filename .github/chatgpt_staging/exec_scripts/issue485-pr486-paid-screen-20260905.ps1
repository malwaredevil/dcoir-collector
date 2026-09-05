[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = 'fd5e4c11f0947b4a3c5c72a308512cfa44cddd3b'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
if ([string]::IsNullOrWhiteSpace([string]$env:OPENROUTER_API_KEY)) { throw 'OPENROUTER_API_KEY is missing from the approved paid-evaluation lane' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr486-paid-screen-' + $requestedSha.Substring(0,12))
$reportPath = Join-Path $downloads 'issue485-pr486-paid-screen.json'
$summaryPath = Join-Path $downloads 'issue485-pr486-paid-screen-summary.json'

try {
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }

    & git -C $repo fetch --no-tags origin $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed with exit code $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed with exit code $LASTEXITCODE" }

    Set-Location -LiteralPath $worktree
    $actualSha = (& git rev-parse HEAD).Trim()
    if ($actualSha -ne $requestedSha) {
        throw "exact-head mismatch: requested=$requestedSha actual=$actualSha"
    }

    $command = @(
        'python3',
        '.github/dcoir_review/scripts/dcoir_review_first_pass_candidate_eval.py',
        '--candidate', 'all',
        '--execute-live',
        '--case', 'pr448-lane-separation-binding',
        '--case', 'pr448-numbered-lifecycle-duplicate',
        '--case', 'rejected-proposition-sibling-branch',
        '--case', 'membership-expression-after-or',
        '--case', 'documented-mode-label-without-runtime-claim',
        '--timeout-seconds', '300',
        '--output', $reportPath
    )
    Write-Host ('Paid candidate screen command: ' + ($command -join ' '))
    & $command[0] $command[1..($command.Count - 1)]
    if ($LASTEXITCODE -ne 0) { throw "candidate screen failed with exit code $LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) { throw 'candidate screen report was not written' }

    $report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$report.mode -ne 'live-no-publication') { throw "unexpected report mode: $($report.mode)" }
    if ($report.no_publication -ne $true) { throw 'candidate screen did not assert no_publication=true' }
    if (@($report.candidates).Count -ne 3) { throw "expected 3 candidate reports, got $(@($report.candidates).Count)" }

    $summaryCandidates = @()
    foreach ($candidateReport in @($report.candidates)) {
        $quality = $candidateReport.quality
        $economics = $candidateReport.economics
        $summaryCandidates += [ordered]@{
            candidate_id = [string]$candidateReport.candidate.id
            model = [string]$candidateReport.candidate.model
            reasoning_effort = [string]$candidateReport.candidate.reasoning_effort
            controlled_known_errors_detected = [int]$quality.controlled_known_errors_detected
            controlled_known_errors_total = [int]$quality.controlled_known_errors_total
            controlled_clean_correct = [int]$quality.controlled_clean_correct
            controlled_clean_total = [int]$quality.controlled_clean_total
            naturalistic_known_defects_detected = [int]$quality.naturalistic_known_defects_detected
            naturalistic_known_defects_total = [int]$quality.naturalistic_known_defects_total
            ambiguous_case_ids = @($quality.ambiguous_case_ids)
            request_error_case_ids = @($quality.request_error_case_ids)
            acceptance_eligible_quality_floor = [bool]$quality.acceptance_eligible_quality_floor
            request_count = [int]$economics.request_count
            prompt_tokens = [long]$economics.prompt_tokens
            completion_tokens = [long]$economics.completion_tokens
            reasoning_tokens = [long]$economics.reasoning_tokens
            cached_prompt_tokens = [long]$economics.cached_prompt_tokens
            total_tokens = [long]$economics.total_tokens
            exact_cost_usd = [double]$economics.exact_cost_usd
            serial_wall_seconds = [double]$economics.serial_wall_seconds
        }
    }

    [ordered]@{
        schema = 'dcoir.issue485.pr486_paid_screen_summary.v1'
        pr_number = 486
        exact_head_sha = $actualSha
        paid_model_inference = $true
        github_review_publication = $false
        selected_case_ids = @(
            'pr448-lane-separation-binding',
            'pr448-numbered-lifecycle-duplicate',
            'rejected-proposition-sibling-branch',
            'membership-expression-after-or',
            'documented-mode-label-without-runtime-claim'
        )
        candidate_count = 3
        expected_request_count = 15
        candidates = $summaryCandidates
    } | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $summaryPath -Encoding utf8

    Write-Host 'Issue #485 / PR #486 paid candidate screen completed without GitHub publication.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }
}
