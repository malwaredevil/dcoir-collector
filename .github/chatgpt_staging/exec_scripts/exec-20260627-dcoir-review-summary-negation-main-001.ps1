[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$RequestId = 'exec-20260627-dcoir-review-summary-negation-main-001'
$RepoRoot = if ([string]::IsNullOrWhiteSpace($env:DCOIR_REPO_ROOT)) { (Get-Location).Path } else { $env:DCOIR_REPO_ROOT }
Set-Location -LiteralPath $RepoRoot

$ReportDir = Join-Path $RepoRoot (Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $RequestId)
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$SummaryPath = Join-Path $ReportDir 'summary_negation_fix.md'
$Log = New-Object 'System.Collections.Generic.List[string]'

function Add-Log {
    param([string]$Text)
    $script:Log.Add($Text)
    Write-Host $Text
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    Add-Log ("$FilePath " + ($Arguments -join ' '))
    $output = & $FilePath @Arguments 2>&1
    $exit = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    foreach ($line in $output) {
        Add-Log ("    " + [string]$line)
    }
    if ($exit -ne 0) {
        throw "$FilePath failed with exit code $exit"
    }
    return $output
}

function Get-BlobSha {
    param([Parameter(Mandatory=$true)][string]$Path)
    $value = & git rev-parse "HEAD:$Path"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read blob SHA for $Path"
    }
    return ([string]$value).Trim()
}

try {
    Add-Log '# DCOIR Review summary negation fix'
    Add-Log "request_id=$RequestId"
    Invoke-Logged -FilePath 'git' -Arguments @('fetch','--no-tags','origin','main') | Out-Null
    Invoke-Logged -FilePath 'git' -Arguments @('checkout','-B','main','origin/main') | Out-Null
    Invoke-Logged -FilePath 'git' -Arguments @('config','user.name','github-actions[bot]') | Out-Null
    Invoke-Logged -FilePath 'git' -Arguments @('config','user.email','41898282+github-actions[bot]@users.noreply.github.com') | Out-Null

    $expected = @{
        '.github/dcoir_review/scripts/openrouter_pr_review_hardened.py' = '1f76d04d83c323755d9964d6ca1a9079b28ab534'
        '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py' = 'f48f858d2930c0227971296dea23fbdfcf6dbeb5'
    }
    foreach ($path in $expected.Keys) {
        $actual = Get-BlobSha -Path $path
        Add-Log "$path blob=$actual"
        if ($actual -ne $expected[$path]) {
            throw "Unexpected blob for $path. Expected $($expected[$path]) but found $actual"
        }
    }

    $patchPath = Join-Path $env:RUNNER_TEMP 'patch_dcoir_summary_negation.py'
    @'
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match for {label}, found {count}")
    return text.replace(old, new)

script_path = Path(".github/dcoir_review/scripts/openrouter_pr_review_hardened.py")
script_text = script_path.read_text(encoding="utf-8")
script_text = replace_once(
    script_text,
    r'''    remaining_problem_noun_pattern = r"(?:issues?|problems?|regressions?|risks?|failures?|bypasses?)"
''',
    r'''    remaining_problem_noun_pattern = r"(?:issues?|problems?|regressions?|risks?|failures?|bypasses?)"
    introduced_problem_noun_pattern = (
        r"(?:findings?|issues?|problems?|defects?|vulnerabilities?|regressions?|risks?|failures?|bypasses?|injection paths?)"
    )
''',
    "introduced problem noun pattern",
)
script_text = replace_once(
    script_text,
    r'''    negated_problem_patterns = (
        *negated_list_patterns,
''',
    r'''    negated_introduced_problem_patterns = (
        rf"\b(?:does not|doesn't)(?: itself)?\s+(?:introduce|create|pose|add)\b"
        rf"(?:(?:\.\d)|[^.;:!?\n]){{0,220}}\b{introduced_problem_noun_pattern}\b",
    )
    negated_problem_patterns = (
        *negated_list_patterns,
        *negated_introduced_problem_patterns,
''',
    "negated introduced problem patterns",
)
script_text = replace_once(
    script_text,
    r'''    cleaned_summary = summary.lower()
    for pattern in negated_list_patterns:
        cleaned_summary = re.sub(pattern, " ", cleaned_summary)
''',
    r'''    cleaned_summary = summary.lower()
    for pattern in (*negated_introduced_problem_patterns, *negated_list_patterns):
        cleaned_summary = re.sub(pattern, " ", cleaned_summary)
''',
    "pre-split negated summary cleanup",
)
script_path.write_text(script_text, encoding="utf-8", newline="\n")

selftest_path = Path(".github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py")
selftest_text = selftest_path.read_text(encoding="utf-8")
selftest_text = replace_once(
    selftest_text,
    r'''    "No regressions found. Security risks remain.",
    "No regressions found, security risks remain.",
''',
    r'''    "No regressions found. Security risks remain.",
    "No regressions found, security risks remain.",
    "The changed code does not introduce compatibility problems. Security risks remain.",
''',
    "problem summary regression guard",
)
selftest_text = replace_once(
    selftest_text,
    r'''    "No regressions found. No security risks remain.",
]:
''',
    r'''    "No regressions found. No security risks remain.",
    "No high-confidence actionable findings. The PR hardens native GitHub suggestion verification by anchoring replacements to the actual file text, reducing the maximum length, blocking multi-line and marker-containing suggestions, and rejecting suggestions when the changed-line count is not exactly one. Both the verifier and the selftest new coverage look correct. The changed code does not introduce any correctness, security, governance, Windows PowerShell 5.1 compatibility, or validation-gap risk.",
]:
''',
    "clean summary decimal negation regression",
)
selftest_path.write_text(selftest_text, encoding="utf-8", newline="\n")
'@ | Out-File -FilePath $patchPath -Encoding utf8

    Add-Log 'phase=apply-patch'
    Invoke-Logged -FilePath 'python' -Arguments @($patchPath) | Out-Null

    Add-Log 'phase=validate'
    Invoke-Logged -FilePath 'python' -Arguments @('-m','py_compile','.github/dcoir_review/scripts/openrouter_pr_review.py','.github/dcoir_review/scripts/openrouter_pr_review_hardened.py','.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py') | Out-Null
    Invoke-Logged -FilePath 'python' -Arguments @('.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py') | Out-Null
    Invoke-Logged -FilePath 'git' -Arguments @('diff','--check','--','.github/dcoir_review/scripts/openrouter_pr_review_hardened.py','.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py') | Out-Null

    $diffStat = & git diff --stat -- .github/dcoir_review/scripts/openrouter_pr_review_hardened.py .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py
    foreach ($line in $diffStat) { Add-Log ("    " + [string]$line) }
    $diffNameOnly = & git diff --name-only -- .github/dcoir_review/scripts/openrouter_pr_review_hardened.py .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py
    if (-not $diffNameOnly) {
        throw 'Patch produced no diff'
    }

    Invoke-Logged -FilePath 'git' -Arguments @('add','--','.github/dcoir_review/scripts/openrouter_pr_review_hardened.py','.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py') | Out-Null
    Invoke-Logged -FilePath 'git' -Arguments @('commit','-m','Handle negated clean DCOIR review summaries') | Out-Null
    $newHead = (& git rev-parse HEAD).Trim()
    Add-Log "new_main_head=$newHead"
    Invoke-Logged -FilePath 'git' -Arguments @('push','origin','HEAD:refs/heads/main') | Out-Null

    @(
        '# DCOIR Review summary negation fix',
        '',
        "- request_id: $RequestId",
        '- result: success',
        "- main_head: $newHead",
        '- changed_files: .github/dcoir_review/scripts/openrouter_pr_review_hardened.py; .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
        '- change: treat negated clean-summary phrases such as does not introduce ... risk as clean before comma/or clause splitting',
        '- validation: py_compile for openrouter_pr_review.py, openrouter_pr_review_hardened.py, openrouter_pr_review_hardened_selftest.py; hardened selftest; git diff --check',
        '',
        '## Timeline',
        '',
        ($Log -join "`n")
    ) | Out-File -FilePath $SummaryPath -Encoding utf8
}
catch {
    @(
        '# DCOIR Review summary negation fix',
        '',
        "- request_id: $RequestId",
        '- result: failure',
        "- error: $($_.Exception.Message)",
        '',
        '## Timeline',
        '',
        ($Log -join "`n")
    ) | Out-File -FilePath $SummaryPath -Encoding utf8
    throw
}
