$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
    }
}

$patchPath = Join-Path $env:TEMP 'dcoir_review_fix_guidance_normalization.py'
@'
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected patch anchor not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


base_path = "scripts/openrouter_pr_review.py"
replace_once(
    base_path,
    '''def fix_guidance_value_text(value: Any, config: Config, *, neutralize_mentions: bool = False) -> str:
    return strip_markdown_fence_lines(
        sanitize_github_output(str(value or "").strip(), config, neutralize_mentions=neutralize_mentions)
    )

def build_inline_comment(finding: dict[str, Any], model_used: str, config: Config) -> str:
''',
    '''def fix_guidance_value_text(value: Any, config: Config, *, neutralize_mentions: bool = False) -> str:
    return strip_markdown_fence_lines(
        sanitize_github_output(str(value or "").strip(), config, neutralize_mentions=neutralize_mentions)
    )


def build_inline_comment(finding: dict[str, Any], model_used: str, config: Config) -> str:
''',
)
replace_once(
    base_path,
    '''    if fix_guidance:
        language = sanitize_github_output(str(fix_guidance.get("language", "text") or "text").strip(), config)
        if not re.fullmatch(r"[A-Za-z0-9_+.-]{1,32}", language):
            language = "text"
        parts.extend(["", "Suggested repair:"])
        for label, key in (("Remove", "remove"), ("Replace", "replace"), ("Add", "add")):
            value = fix_guidance_value_text(fix_guidance.get(key, ""), config, neutralize_mentions=False)
            if value:
                parts.extend(["", f"{label}:", "", f"```{language}", value, "```"])
        notes = fix_guidance_value_text(fix_guidance.get("notes", ""), config)
        if notes:
            parts.extend(["", notes])
''',
    '''    if fix_guidance:
        parts.extend(["", "Suggested repair:"])
        for label, key in (("Remove", "remove"), ("Replace", "replace"), ("Add", "add")):
            value = fix_guidance_value_text(fix_guidance.get(key, ""), config, neutralize_mentions=False)
            if value:
                parts.extend(["", f"{label}:", "", "```text", value, "```"])
        notes = fix_guidance_value_text(fix_guidance.get("notes", ""), config)
        if notes:
            parts.extend(["", "Notes:", "", "```text", notes, "```"])
''',
)

pareto_path = "scripts/openrouter_pr_review_pareto_context.py"
replace_once(
    pareto_path,
    '''- Do not include Markdown fences in JSON fields.
- Do not repeat secret-like literal values.
''',
    '''- Do not include Markdown fences in JSON fields.
- For eval/exec/dynamic code execution findings, do not propose another eval or exec call, even with restricted globals. Prefer removal, ast.literal_eval for literal-only data, a constrained parser/AST allowlist, or an explicit allowlist.
- Do not repeat secret-like literal values.
''',
)
replace_once(
    pareto_path,
    '''def fix_guidance_from_result(fix_result: dict[str, Any], path: str, config: Any) -> dict[str, str]:
''',
    '''PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN = re.compile(r"\\b(?:eval|exec)\\s*\\(")


def is_python_dynamic_exec_fix_scope(finding: dict[str, Any], path: str, line_text: str) -> bool:
    if Path(path).suffix.lower() != ".py":
        return False
    haystack = "\\n".join(
        [
            str(finding.get("title", "") or ""),
            str(finding.get("body", "") or ""),
            str(finding.get("validation", "") or ""),
            line_text,
        ]
    ).lower()
    if PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN.search(line_text):
        return True
    return ("eval" in haystack or "exec" in haystack) and (
        "dynamic" in haystack or "code execution" in haystack or "arbitrary code" in haystack
    )


def harden_python_dynamic_exec_fix_result(
    fix_result: dict[str, Any],
    finding: dict[str, Any],
    path: str,
    line_text: str,
) -> dict[str, Any]:
    if not isinstance(fix_result, dict) or not is_python_dynamic_exec_fix_scope(finding, path, line_text):
        return fix_result
    result = dict(fix_result)
    result["suggested_replacement"] = ""
    result["remove"] = str(
        result.get("remove")
        or f"Remove the dynamic Python execution call on the anchored line: {line_text.strip()}"
    ).strip()
    result["replace"] = (
        "Replace the dynamic evaluation with a non-executing parser or explicit allowlist. "
        "Use ast.literal_eval only for literal data; for expression-like input, implement a constrained AST "
        "or grammar allowlist. Do not use eval or exec, even with restricted globals."
    )
    add_text = str(result.get("add", "") or "").strip()
    if not add_text or PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN.search(add_text):
        result["add"] = (
            "Add tests proving os, __import__, open, and filesystem side effects are rejected "
            "without being executed."
        )
    else:
        result["add"] = add_text
    result["notes"] = (
        "Native GitHub suggestion suppressed because the safe repair depends on approved expression semantics; "
        "do not replace eval or exec with another dynamic execution primitive."
    )
    return result


def fix_guidance_from_result(fix_result: dict[str, Any], path: str, config: Any) -> dict[str, str]:
''',
)
replace_once(
    pareto_path,
    '''    result, model_used, service_tier = hardened.openrouter_review(prompt, schema, config, reporter=None)
    hardened.write_debug_json_artifact_safely(
''',
    '''    result, model_used, service_tier = hardened.openrouter_review(prompt, schema, config, reporter=None)
    result = harden_python_dynamic_exec_fix_result(result, finding, path, line_text)
    hardened.write_debug_json_artifact_safely(
''',
)

selftest_path = "scripts/openrouter_pr_review_pareto_context_selftest.py"
replace_once(
    selftest_path,
    '''assert "Keep the repair limited" in fallback_fix_comment
assert "```suggestion" not in fallback_fix_comment

malformed_guidance_comment = mod.base.build_inline_comment(
''',
    '''assert "Keep the repair limited" in fallback_fix_comment
assert "```suggestion" not in fallback_fix_comment
assert "Notes:" in fallback_fix_comment
assert "```text\\nKeep the repair limited to the deserialization path.\\n```" in fallback_fix_comment

malformed_guidance_comment = mod.base.build_inline_comment(
''',
)
replace_once(
    selftest_path,
    '''assert 'python3 -m py_compile project_sources/collector/tools/dcoir_review_intentional_python_probe.py && python3 -c "' not in malformed_guidance_comment
assert "bandit -r project_sources/collector/tools/dcoir_review_intentional_python_probe.py" in malformed_guidance_comment

try:
''',
    '''assert 'python3 -m py_compile project_sources/collector/tools/dcoir_review_intentional_python_probe.py && python3 -c "' not in malformed_guidance_comment
assert "bandit -r project_sources/collector/tools/dcoir_review_intentional_python_probe.py" in malformed_guidance_comment

heading_notes_comment = mod.base.build_inline_comment(
    {
        "title": "Global state write",
        "severity": "high",
        "confidence": 0.95,
        "body": "Fallback notes must not escape into markdown headings.",
        "validation": "pwsh -NoProfile -Command 'Invoke-ScriptAnalyzer -Path \"probe.ps1\"'",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "powershell",
            "remove": "Remove the global write.",
            "notes": "# The function should record state through governed storage, not global scope.",
        },
    },
    "test-model",
    config,
)
assert "Notes:" in heading_notes_comment
assert "```text\\n# The function should record state through governed storage, not global scope.\\n```" in heading_notes_comment

eval_hardened_fix = mod.harden_python_dynamic_exec_fix_result(
    {
        "suggested_replacement": "return eval(expression, {'__builtins__': {}})",
        "replace": "Replace with `return eval(expression, {'__builtins__': {}}, {})`.",
        "notes": "Restricted globals make this safe.",
    },
    {
        "title": "Arbitrary Python code execution via eval on caller-controlled expression",
        "body": "eval runs caller-controlled Python code.",
        "validation": "python3 -m py_compile probe.py",
    },
    "project_sources/collector/tools/dcoir_review_intentional_python_probe.py",
    "    return eval(expression, {'__builtins__': __builtins__, 'os': os, 'Path': Path})",
)
assert eval_hardened_fix["suggested_replacement"] == ""
assert "eval(" not in eval_hardened_fix["replace"]
assert "exec(" not in eval_hardened_fix["replace"]
assert "ast.literal_eval" in eval_hardened_fix["replace"]
assert "Restricted globals make this safe" not in eval_hardened_fix["notes"]

try:
''',
)
'@ | Set-Content -LiteralPath $patchPath -Encoding UTF8

Invoke-Native -FilePath 'python' -ArgumentList @($patchPath)
Invoke-Native -FilePath 'python' -ArgumentList @('-m', 'py_compile', 'scripts/openrouter_pr_review.py', 'scripts/openrouter_pr_review_pareto_context.py', 'scripts/openrouter_pr_review_pareto_context_selftest.py')
Invoke-Native -FilePath 'python' -ArgumentList @('scripts/openrouter_pr_review_pareto_context_selftest.py')
Invoke-Native -FilePath 'git' -ArgumentList @('diff', '--check', '--', 'scripts/openrouter_pr_review.py', 'scripts/openrouter_pr_review_pareto_context.py', 'scripts/openrouter_pr_review_pareto_context_selftest.py')
Invoke-Native -FilePath 'git' -ArgumentList @('diff', '--', 'scripts/openrouter_pr_review.py', 'scripts/openrouter_pr_review_pareto_context.py', 'scripts/openrouter_pr_review_pareto_context_selftest.py')
Invoke-Native -FilePath 'git' -ArgumentList @('status', '--short')
& git diff --quiet -- scripts/openrouter_pr_review.py scripts/openrouter_pr_review_pareto_context.py scripts/openrouter_pr_review_pareto_context_selftest.py
$diffExit = $LASTEXITCODE
if ($diffExit -eq 0) {
    Write-Host 'No source changes detected after patch; nothing to commit.'
    exit 0
}
if ($diffExit -ne 1) {
    throw "git diff --quiet failed with exit code $diffExit"
}
Invoke-Native -FilePath 'git' -ArgumentList @('config', 'user.name', 'dcoir-chatgpt-exec')
Invoke-Native -FilePath 'git' -ArgumentList @('config', 'user.email', 'dcoir-chatgpt-exec@users.noreply.github.com')
Invoke-Native -FilePath 'git' -ArgumentList @('add', 'scripts/openrouter_pr_review.py', 'scripts/openrouter_pr_review_pareto_context.py', 'scripts/openrouter_pr_review_pareto_context_selftest.py')
Invoke-Native -FilePath 'git' -ArgumentList @('commit', '-m', 'Normalize dcoir-review fix guidance')
Invoke-Native -FilePath 'git' -ArgumentList @('push', 'origin', 'HEAD:main')
