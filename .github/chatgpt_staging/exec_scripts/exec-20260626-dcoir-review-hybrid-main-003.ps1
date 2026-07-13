$ErrorActionPreference = 'Stop'

git config core.autocrlf false
git config core.eol lf
git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
git checkout -B main origin/main
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

$py = @'
from pathlib import Path

review_script_path = Path('.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py')
config_path = Path('.github/dcoir_review/openrouter-pr-review-pareto.yml')
selftest_path = Path('.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py')
readme_path = Path('.github/ops/requests/apply_patch/README.md')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'could not find {label}')
    return text.replace(old, new, 1)


review_text = review_script_path.read_text(encoding='utf-8')
if 'REQUIRED_FINDING_FAMILIES' not in review_text:
    anchor = 'REVIEW_ASSIST_CONTEXT_REPORT = Path("project_sources/collector/powershell_review_assist_workflow_report.md")\n'
    review_text = replace_once(
        review_text,
        anchor,
        anchor
        + 'REQUIRED_FINDING_FAMILIES = ("powershell", "python", "github-actions-yaml")\n'
        + 'OPTIONAL_FINDING_FAMILIES = ("typescript", "kubernetes-yaml")\n',
        'finding family constants insertion point',
    )

if 'config.required_finding_reserved_budget' not in review_text:
    old = '    config.fix_synthesis_min_confidence = float(data.get("fix_synthesis_min_confidence", 0.80))\n'
    new = (
        old
        + '    config.required_finding_reserved_budget = int(\n'
        + '        data.get("required_finding_reserved_budget", min(getattr(config, "max_inline_comments", 12), 9))\n'
        + '    )\n'
        + '    config.required_finding_min_per_family = int(data.get("required_finding_min_per_family", 2))\n'
    )
    review_text = replace_once(review_text, old, new, 'required finding config insertion point')

ranking_functions = '''def normalized_finding_text(value: Any, max_chars: int = 240) -> str:
    return re.sub(r"\\s+", " ", str(value or "").strip().lower())[:max_chars]


def finding_review_family(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "").strip()
    lower_path = path.lower()
    suffix = Path(lower_path).suffix
    title = str(finding.get("title", "") or "")
    body = str(finding.get("body", "") or "")
    haystack = f"{title}\\n{body}".lower()
    if suffix in {".ps1", ".psm1", ".psd1"}:
        return "powershell"
    if suffix == ".py":
        return "python"
    if suffix in {".yml", ".yaml"}:
        if (
            lower_path.startswith(".github/workflows/")
            or "github action" in haystack
            or "workflow" in Path(lower_path).name
            or "/actions/" in lower_path
        ):
            return "github-actions-yaml"
        if (
            "kubernetes" in lower_path
            or lower_path.startswith("k8s/")
            or "/k8s/" in lower_path
            or "kubernetes" in haystack
            or "kubectl" in haystack
        ):
            return "kubernetes-yaml"
        return "yaml"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        return "typescript"
    return "other"


def finding_dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(finding.get("path", "") or "").strip(),
        str(finding.get("line", "") or "").strip(),
        normalized_finding_text(finding.get("title", "")),
        normalized_finding_text(finding.get("body", "")),
    )


def dedupe_findings_for_ranking(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for finding in findings:
        key = finding_dedupe_key(finding)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def rank_findings_for_required_budget(findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    max_inline = max(0, int(getattr(config, "max_inline_comments", 12)))
    if max_inline <= 0:
        return []
    ranked = sorted(dedupe_findings_for_ranking(findings), key=hardened.severity_sort_key)
    if len(ranked) <= max_inline:
        return ranked
    reserved_budget = min(
        max_inline,
        max(0, int(getattr(config, "required_finding_reserved_budget", min(max_inline, 9)))),
    )
    min_per_family = max(0, int(getattr(config, "required_finding_min_per_family", 2)))
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str]] = set()

    def maybe_select(finding: dict[str, Any]) -> bool:
        key = finding_dedupe_key(finding)
        if key in selected_keys:
            return False
        selected.append(finding)
        selected_keys.add(key)
        return True

    if min_per_family > 0:
        for family in REQUIRED_FINDING_FAMILIES:
            family_count = 0
            for finding in ranked:
                if len(selected) >= reserved_budget or family_count >= min_per_family:
                    break
                if finding_review_family(finding) == family and maybe_select(finding):
                    family_count += 1
    for finding in ranked:
        if len(selected) >= reserved_budget:
            break
        if finding_review_family(finding) in REQUIRED_FINDING_FAMILIES:
            maybe_select(finding)
    for finding in ranked:
        if len(selected) >= max_inline:
            break
        maybe_select(finding)
    return selected
'''

if 'def rank_findings_for_required_budget' not in review_text:
    anchor = '    changes = int(item.get("changes") or 0)\n    return family, -changes, path\n\n\n'
    review_text = replace_once(review_text, anchor, anchor + ranking_functions + '\n\n', 'ranking function insertion point')

strip_function = '''def strip_detector_suggested_replacements(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        detector_suggestion = str(item.get("suggested_replacement", "") or "")
        if detector_suggestion.strip():
            item["_detector_suggested_replacement"] = detector_suggestion
            item["suggested_replacement"] = ""
        enriched.append(item)
    return enriched
'''

if 'def strip_detector_suggested_replacements' not in review_text:
    review_text = replace_once(
        review_text,
        '\ndef synthesize_fixes_for_findings(\n',
        '\n' + strip_function + '\n\ndef synthesize_fixes_for_findings(\n',
        'detector suggestion stripping insertion point',
    )

old = '''    if not getattr(config, "fix_synthesis_enabled", True) or not findings:
        return findings
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return findings
'''
new = '''    enriched = strip_detector_suggested_replacements(findings)
    if not getattr(config, "fix_synthesis_enabled", True) or not enriched:
        return enriched
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return enriched
'''
if old in review_text:
    review_text = review_text.replace(old, new, 1)
review_text = review_text.replace('    for index, finding in enumerate(findings):\n', '    for index, finding in enumerate(enriched):\n', 1)
review_text = review_text.replace('    if not candidates:\n        return findings\n', '    if not candidates:\n        return enriched\n', 1)
review_text = review_text.replace('    enriched = [dict(finding) for finding in findings]\n', '', 1)
review_text = review_text.replace('                path = str(findings[index].get("path", "") or "")\n', '                path = str(enriched[index].get("path", "") or "")\n', 1)

split_function = '''def split_findings_with_review_body_fallback(
    result: dict[str, Any],
    config: Any,
    line_index: dict[tuple[str, int], int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list) or not raw_findings:
        return hardened.split_findings(result, config, line_index)
    changed_paths = {path for path, _line in line_index}
    findings: list[dict[str, Any]] = []
    unanchored_findings: list[dict[str, Any]] = []
    track_unanchored = bool(getattr(config, "fail_on_unanchored_findings", True))
    for item in raw_findings:
        try:
            confidence = float(item.get("confidence", 0))
            line = int(item.get("line", 0))
            path = str(item.get("path", "")).strip()
        except (AttributeError, TypeError, ValueError):
            continue
        if not path or line <= 0:
            continue
        if confidence < config.minimum_confidence or hardened.non_actionable_finding_reason(item):
            continue
        if path not in changed_paths:
            continue
        if (path, line) in line_index:
            findings.append(dict(item))
            continue
        if track_unanchored:
            unanchored = dict(item)
            location_text = hardened.finding_location_text(path, line)
            unanchored["_unanchored_reason"] = f"{location_text} is outside the added changed lines for this PR"
            unanchored_findings.append(unanchored)
    findings = rank_findings_for_required_budget(findings, config)
    unanchored_findings = dedupe_findings_for_ranking(unanchored_findings)
    unanchored_findings.sort(key=hardened.severity_sort_key)
    unanchored_findings = unanchored_findings[: config.max_inline_comments]
    if findings or unanchored_findings:
        return findings, unanchored_findings
    return hardened.split_findings(result, config, line_index)
'''

split_start = review_text.index('def split_findings_with_review_body_fallback(')
split_end_marker = '\n\n\ndef review_assist_context_path'
split_end = review_text.index(split_end_marker, split_start)
review_text = review_text[:split_start] + split_function + review_text[split_end:]
review_script_path.write_text(review_text, encoding='utf-8')

config_text = config_path.read_text(encoding='utf-8')
if 'required_finding_reserved_budget:' not in config_text:
    needle = 'fix_synthesis_min_confidence: 0.80\n\nrequest_changes_on_findings: false\n'
    replacement = (
        'fix_synthesis_min_confidence: 0.80\n'
        'required_finding_reserved_budget: 9\n'
        'required_finding_min_per_family: 2\n\n'
        'request_changes_on_findings: false\n'
    )
    config_text = replace_once(config_text, needle, replacement, 'config insertion point')
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
    selftest_text = replace_once(selftest_text, needle, replacement, 'config assertion insertion point')

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
    selftest_text = replace_once(selftest_text, needle, test_block + needle, 'selftest final print insertion point')
selftest_path.write_text(selftest_text, encoding='utf-8')

readme_text = readme_path.read_text(encoding='utf-8')
if 'blank context lines inside a hunk must still begin with a single space' not in readme_text:
    needle = (
        'Git normalizes line endings.\n\n'
        'Use `mode: "dry-run"` to validate and run `git apply --check` without committing.\n'
    )
    addition = (
        'Git normalizes line endings.\n\n'
        'The patch file must be a valid unified diff. Context lines, including\n'
        'blank context lines inside a hunk must still begin with a single space;\n'
        'added lines begin with `+` and removed lines begin with `-`. A patch can\n'
        'pass checksum validation but still fail `git apply --check` as corrupt\n'
        'when a staged hunk contains bare empty lines instead of space-prefixed\n'
        'blank context lines.\n\n'
        'Use `mode: "dry-run"` to validate and run `git apply --check` without committing.\n'
    )
    readme_text = replace_once(readme_text, needle, addition, 'apply-patch README formatting note insertion point')
    readme_path.write_text(readme_text, encoding='utf-8')
'@
$tool = Join-Path $env:RUNNER_TEMP 'dcoir_review_direct_update.py'
Set-Content -LiteralPath $tool -Value $py -Encoding UTF8
python $tool
if ($LASTEXITCODE -ne 0) { throw 'direct source update failed' }

python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
if ($LASTEXITCODE -ne 0) { throw 'pareto context selftest failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }

git add .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/openrouter-pr-review-pareto.yml .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py .github/ops/requests/apply_patch/README.md
git rm -r --ignore-unmatch -- .github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001

$staged = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace(($staged -join "`n"))) {
  throw 'no changes staged for DCOIR Review hybrid update'
}

git commit -m 'Implement DCOIR review hybrid ranking and fix synthesis guard'
git push origin HEAD:refs/heads/main
git rev-parse HEAD
