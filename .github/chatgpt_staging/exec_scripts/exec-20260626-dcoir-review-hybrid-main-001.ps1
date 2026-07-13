$ErrorActionPreference = 'Stop'
$request = '.github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001/request.json'
$report = '.github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-001/ops-apply-patch'
python .github/ops/tools/apply_patch_request.py validate --repo . --request $request --default-branch main
if ($LASTEXITCODE -ne 0) { throw 'apply-patch validation failed' }
python .github/ops/tools/apply_patch_request.py apply --repo . --request $request --default-branch main --report-dir $report
if ($LASTEXITCODE -ne 0) { throw 'apply-patch apply failed' }

git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
git checkout -B main origin/main

$py = @'
from pathlib import Path

def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing expected text in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    ".github/dcoir_review/openrouter-pr-review-pareto.yml",
    "fix_synthesis_min_confidence: 0.80\n\nrequest_changes_on_findings: false\n",
    "fix_synthesis_min_confidence: 0.80\nrequired_finding_reserved_budget: 9\nrequired_finding_min_per_family: 2\n\nrequest_changes_on_findings: false\n",
)

replace_once(
    ".github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py",
    "assert config.post_progress_comment is False\n\ntry:\n",
    "assert config.post_progress_comment is False\nassert config.required_finding_reserved_budget == 9\nassert config.required_finding_min_per_family == 2\n\ntry:\n",
)

budget_test = r'''
budget_config = mod.copy.copy(config)
budget_config.max_inline_comments = 3
budget_config.required_finding_reserved_budget = 3
budget_config.required_finding_min_per_family = 1
budget_result = {
    "summary": "Review found mixed-language issues.",
    "findings": [
        {"path": "ui/widget.ts", "line": 10, "severity": "critical", "confidence": 0.99, "title": "TS optional", "body": "Optional TypeScript issue."},
        {"path": "charts/deploy.yaml", "line": 20, "severity": "critical", "confidence": 0.99, "title": "Kubernetes optional", "body": "Optional kubernetes issue."},
        {"path": "scripts/fix.ps1", "line": 30, "severity": "high", "confidence": 0.95, "title": "PowerShell required", "body": "Required PowerShell issue."},
        {"path": "tools/fix.py", "line": 40, "severity": "medium", "confidence": 0.95, "title": "Python required", "body": "Required Python issue."},
        {"path": ".github/workflows/review.yml", "line": 50, "severity": "medium", "confidence": 0.95, "title": "Workflow required", "body": "Required GitHub Actions workflow issue."},
    ],
}
budget_index = {
    ("ui/widget.ts", 10): 1,
    ("charts/deploy.yaml", 20): 2,
    ("scripts/fix.ps1", 30): 3,
    ("tools/fix.py", 40): 4,
    (".github/workflows/review.yml", 50): 5,
}
budget_inline, budget_unanchored = mod.split_findings_with_review_body_fallback(budget_result, budget_config, budget_index)
assert budget_unanchored == []
assert {mod.finding_review_family(item) for item in budget_inline} == set(mod.REQUIRED_FINDING_FAMILIES)

disabled_fix_config = mod.copy.copy(config)
disabled_fix_config.fix_synthesis_enabled = False
stripped = mod.synthesize_fixes_for_findings(
    [{"path": "tools/fix.py", "line": 1, "severity": "high", "confidence": 0.99, "title": "Detector suggestion", "body": "Detector should not own fixes.", "suggested_replacement": "print('unsafe')"}],
    None,
    {},
    {},
    disabled_fix_config,
    mock.Mock(),
)
assert stripped[0]["suggested_replacement"] == ""
assert stripped[0]["_detector_suggested_replacement"] == "print('unsafe')"

'''
replace_once(
    ".github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py",
    'assert "not an added changed line" in review_body_findings[0]["_unanchored_reason"]\n\nprint("Pareto context DCOIR Review selftest passed")\n',
    'assert "not an added changed line" in review_body_findings[0]["_unanchored_reason"]\n\n' + budget_test + 'print("Pareto context DCOIR Review selftest passed")\n',
)
'@

$tool = Join-Path $env:RUNNER_TEMP 'finish_dcoir_review_hybrid.py'
Set-Content -LiteralPath $tool -Value $py -Encoding UTF8
python $tool
python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
python .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
git diff --check
git add .github/dcoir_review/openrouter-pr-review-pareto.yml .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
git rm -r --ignore-unmatch -- .github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001
git commit -m 'Configure and test DCOIR review required finding budget'
git push origin HEAD:refs/heads/main
git rev-parse HEAD
