$ErrorActionPreference = 'Stop'

$request = '.github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001/request.json'
$applyReport = '.github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-002/ops-apply-patch'
$reviewScript = '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py'

# Keep checkout bytes deterministic for unified patch application.
git config core.autocrlf false
git config core.eol lf
git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
git checkout -B main origin/main

$scriptAlreadyPatched = Select-String -LiteralPath $reviewScript -Pattern 'REQUIRED_FINDING_FAMILIES' -Quiet
if (-not $scriptAlreadyPatched) {
  if (-not (Test-Path -LiteralPath $request -PathType Leaf)) {
    throw "apply-patch request is missing and $reviewScript is not patched"
  }
  python .github/ops/tools/apply_patch_request.py validate --repo . --request $request --default-branch main
  if ($LASTEXITCODE -ne 0) { throw 'apply-patch validation failed' }
  python .github/ops/tools/apply_patch_request.py apply --repo . --request $request --default-branch main --report-dir $applyReport
  if ($LASTEXITCODE -ne 0) { throw 'apply-patch apply failed' }
}

# Continue from the live branch head after the apply-patch helper pushes.
git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
git checkout -B main origin/main
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

$py = @'
from pathlib import Path

config_path = Path('.github/dcoir_review/openrouter-pr-review-pareto.yml')
selftest_path = Path('.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py')

config_text = config_path.read_text(encoding='utf-8')
if 'required_finding_reserved_budget:' not in config_text:
    needle = 'fix_synthesis_min_confidence: 0.80\n\nrequest_changes_on_findings: false\n'
    replacement = (
        'fix_synthesis_min_confidence: 0.80\n'
        'required_finding_reserved_budget: 9\n'
        'required_finding_min_per_family: 2\n\n'
        'request_changes_on_findings: false\n'
    )
    if needle not in config_text:
        raise SystemExit('could not find config insertion point')
    config_text = config_text.replace(needle, replacement, 1)
    config_path.write_text(config_text, encoding='utf-8')

selftest_text = selftest_path.read_text(encoding='utf-8')
if 'config.required_finding_reserved_budget == 9' not in selftest_text:
    needle = 'assert config.post_progress_comment is False\n'
    replacement = (
        'assert config.post_progress_comment is False\n'
        'assert config.per_file_first_pass_review is True\n'
        'assert config.per_file_review_concurrency == 4\n'
        'assert config.fix_synthesis_enabled is True\n'
        'assert config.required_finding_reserved_budget == 9\n'
        'assert config.required_finding_min_per_family == 2\n'
    )
    if needle not in selftest_text:
        raise SystemExit('could not find config assertion insertion point')
    selftest_text = selftest_text.replace(needle, replacement, 1)

if 'ranked_required_budget_findings = mod.rank_findings_for_required_budget' not in selftest_text:
    needle = '\nprint("Pareto context DCOIR Review selftest passed")\n'
    test_block = r'''

ranking_budget_config = mod.copy.copy(config)
ranking_budget_config.max_inline_comments = 5
ranking_budget_config.required_finding_reserved_budget = 5
ranking_budget_config.required_finding_min_per_family = 1
ranking_budget_findings = [
    {
        "path": "web/app.ts",
        "line": 10,
        "severity": "high",
        "confidence": 0.99,
        "title": "Optional TypeScript finding",
        "body": "Optional TypeScript issue should not crowd out required operational families.",
    },
    {
        "path": "k8s/deployment.yaml",
        "line": 11,
        "severity": "high",
        "confidence": 0.99,
        "title": "Optional Kubernetes finding",
        "body": "Optional Kubernetes issue should stay behind required operational families when budget is tight.",
    },
    {
        "path": "scripts/ops.ps1",
        "line": 12,
        "severity": "medium",
        "confidence": 0.96,
        "title": "PowerShell finding",
        "body": "PowerShell operational risk must keep a reserved slot.",
    },
    {
        "path": "scripts/check.py",
        "line": 13,
        "severity": "medium",
        "confidence": 0.96,
        "title": "Python finding",
        "body": "Python operational risk must keep a reserved slot.",
    },
    {
        "path": ".github/workflows/ci.yml",
        "line": 14,
        "severity": "medium",
        "confidence": 0.96,
        "title": "GitHub Actions finding",
        "body": "GitHub Actions workflow risk must keep a reserved slot.",
    },
    {
        "path": "web/extra.ts",
        "line": 15,
        "severity": "medium",
        "confidence": 0.95,
        "title": "Second TypeScript finding",
        "body": "Extra optional issue competes only after required families are represented.",
    },
]
ranked_required_budget_findings = mod.rank_findings_for_required_budget(ranking_budget_findings, ranking_budget_config)
ranked_required_families = [mod.finding_review_family(item) for item in ranked_required_budget_findings]
assert len(ranked_required_budget_findings) == 5
assert "powershell" in ranked_required_families
assert "python" in ranked_required_families
assert "github-actions-yaml" in ranked_required_families
assert ranked_required_families.index("powershell") < 5
assert ranked_required_families.index("python") < 5
assert ranked_required_families.index("github-actions-yaml") < 5

original_detector_findings = [
    {
        "path": "scripts/ops.ps1",
        "line": 42,
        "severity": "high",
        "confidence": 0.79,
        "title": "Detector-proposed fix",
        "body": "Detector pass should not be trusted to provide a native GitHub suggestion.",
        "suggested_replacement": "Write-Output 'fixed'",
    }
]
stripped_detector_findings = mod.strip_detector_suggested_replacements(original_detector_findings)
assert original_detector_findings[0]["suggested_replacement"] == "Write-Output 'fixed'"
assert stripped_detector_findings[0]["suggested_replacement"] == ""
assert stripped_detector_findings[0]["_detector_suggested_replacement"] == "Write-Output 'fixed'"
'''
    if needle not in selftest_text:
        raise SystemExit('could not find selftest final print insertion point')
    selftest_text = selftest_text.replace(needle, test_block + needle, 1)

selftest_path.write_text(selftest_text, encoding='utf-8')
'@
$tool = Join-Path $env:RUNNER_TEMP 'dcoir_review_config_selftest_update.py'
Set-Content -LiteralPath $tool -Value $py -Encoding UTF8
python $tool
if ($LASTEXITCODE -ne 0) { throw 'config/selftest update failed' }

python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
if ($LASTEXITCODE -ne 0) { throw 'pareto context selftest failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }

git add .github/dcoir_review/openrouter-pr-review-pareto.yml .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
git rm -r --ignore-unmatch -- .github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001

$staged = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace(($staged -join "`n"))) {
  Write-Host 'No config/selftest/cleanup changes remained to commit.'
} else {
  git commit -m 'Configure and test DCOIR review required finding budget'
  git push origin HEAD:refs/heads/main
}

git rev-parse HEAD
