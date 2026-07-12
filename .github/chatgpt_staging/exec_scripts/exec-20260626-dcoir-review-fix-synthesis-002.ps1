$ErrorActionPreference = 'Stop'
$requestId = 'exec-20260626-dcoir-review-fix-synthesis-002'
$branch = 'fix/dcoir-review-fix-synthesis-verifier-20260626'
$runnerPath = '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py'
$selftestPath = '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py'
$basePath = '.github/dcoir_review/scripts/openrouter_pr_review.py'
$expectedRunnerBlob = '05ea1efa90dfa3f34e36b5c9dfd05a8861c5c16a'
$expectedSelftestBlob = 'f713c827409cd79817d91d9fe7d2a4d82e055f01'

function Invoke-Git([string[]]$GitArgs) {
  Write-Host "git $($GitArgs -join ' ')"
  $output = & git @GitArgs
  $code = $LASTEXITCODE
  if ($output) { $output | Out-Host }
  if ($code -ne 0) { throw "git failed with exit $code`: git $($GitArgs -join ' ')" }
}

function Get-TrackedBlob([string]$Path) {
  $line = (& git ls-files -s -- $Path)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($line)) { throw "Unable to read tracked blob for $Path" }
  return (($line -split '\s+')[1])
}

function Assert-Blob([string]$Path, [string]$Expected) {
  $actual = Get-TrackedBlob -Path $Path
  Write-Host "$Path blob=$actual"
  if ($actual -ne $Expected) { throw "Blob mismatch for $Path expected $Expected got $actual" }
}

try {
  Invoke-Git @('fetch', '--no-tags', 'origin', 'main')
  Invoke-Git @('checkout', '-B', $branch, 'origin/main')
  Invoke-Git @('config', 'user.name', 'github-actions[bot]')
  Invoke-Git @('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
  Assert-Blob -Path $runnerPath -Expected $expectedRunnerBlob
  Assert-Blob -Path $selftestPath -Expected $expectedSelftestBlob

  $editScript = @'
from pathlib import Path

runner = Path(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py")
selftest = Path(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py")

runner_text = runner.read_text(encoding="utf-8")
old_verifier = '''def verified_suggested_replacement(fix_result: dict[str, Any], line_text: str, config: Any) -> str:
    suggestion = str(fix_result.get("suggested_replacement", "") or "").rstrip()
    if not suggestion:
        return ""
    if "```" in suggestion:
        return ""
    if len(suggestion) > 5000 or suggestion.count("\n") > 80:
        return ""
    if not base.is_safe_suggestion(suggestion):
        return ""
    if suggestion.strip() == line_text.strip():
        return ""
    return suggestion
'''
new_verifier = '''def verified_suggested_replacement(fix_result: dict[str, Any], file_text: str, line_number: int, config: Any) -> str:
    suggestion = str(fix_result.get("suggested_replacement", "") or "").rstrip()
    if not suggestion:
        return ""
    if "```" in suggestion or "\r" in suggestion or "\n" in suggestion:
        return ""
    if len(suggestion) > 1000:
        return ""
    if not base.is_safe_suggestion(suggestion):
        return ""
    original_line = file_line_text(file_text, line_number)
    if not original_line:
        return ""
    if suggestion.strip() == original_line.strip():
        return ""
    lines = file_text.splitlines()
    if line_number <= 0 or line_number > len(lines):
        return ""
    updated_lines = list(lines)
    updated_lines[line_number - 1] = suggestion
    changed_lines = [
        index
        for index, (before, after) in enumerate(zip(lines, updated_lines), start=1)
        if before != after
    ]
    if changed_lines != [line_number]:
        return ""
    return suggestion
'''
if old_verifier not in runner_text:
    raise SystemExit("expected existing verified_suggested_replacement body was not found")
runner_text = runner_text.replace(old_verifier, new_verifier, 1)
old_call = "    suggestion = verified_suggested_replacement(result, line_text, config)\n"
new_call = "    suggestion = verified_suggested_replacement(result, file_text, line, config)\n"
if old_call not in runner_text:
    raise SystemExit("expected fix-synthesis verifier call was not found")
runner_text = runner_text.replace(old_call, new_call, 1)
runner.write_text(runner_text, encoding="utf-8")

selftest_text = selftest.read_text(encoding="utf-8")
marker = 'fix_synthesis_verifier_marker = "single-line-pr-head-anchor"'
if marker in selftest_text:
    raise SystemExit("fix-synthesis verifier selftest block is already present")
anchor = "assert config.required_finding_min_per_family == 2\n"
insert = '''

fix_synthesis_verifier_marker = "single-line-pr-head-anchor"
fix_file_text = "def restore(raw_state):\n    state = pickle.loads(raw_state)\n    return state\n"
fix_replacement = "    state = json.loads(raw_state)"
assert mod.verified_suggested_replacement(
    {"suggested_replacement": fix_replacement},
    fix_file_text,
    2,
    config,
) == fix_replacement
assert mod.verified_suggested_replacement(
    {"suggested_replacement": "    state = pickle.loads(raw_state)"},
    fix_file_text,
    2,
    config,
) == ""
assert mod.verified_suggested_replacement(
    {"suggested_replacement": "    state = json.loads(raw_state)\n    return state"},
    fix_file_text,
    2,
    config,
) == ""
assert mod.verified_suggested_replacement(
    {"suggested_replacement": "```python\nstate = json.loads(raw_state)\n```"},
    fix_file_text,
    2,
    config,
) == ""
assert mod.verified_suggested_replacement(
    {"suggested_replacement": "Use json.loads instead"},
    fix_file_text,
    2,
    config,
) == ""
assert mod.verified_suggested_replacement(
    {"suggested_replacement": fix_replacement},
    fix_file_text,
    99,
    config,
) == ""

native_fix_comment = mod.base.build_inline_comment(
    {
        "title": "Unsafe deserialization",
        "severity": "high",
        "confidence": 0.95,
        "body": "The changed line deserializes untrusted state.",
        "validation": "python3 -m py_compile .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py",
        "suggested_replacement": fix_replacement,
    },
    "test-model",
    config,
)
assert "```suggestion\n    state = json.loads(raw_state)\n```" in native_fix_comment

fallback_fix_comment = mod.base.build_inline_comment(
    {
        "title": "Unsafe deserialization",
        "severity": "high",
        "confidence": 0.95,
        "body": "The changed line needs a broader repair than one line.",
        "validation": "python3 -m py_compile .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "python",
            "remove": "pickle.loads(raw_state)",
            "replace": "json.loads(raw_state)",
            "add": "Add a JSON schema validation test for the accepted state shape.",
            "notes": "Keep the repair limited to the deserialization path.",
        },
    },
    "test-model",
    config,
)
assert "Suggested repair:" in fallback_fix_comment
assert "Remove:" in fallback_fix_comment
assert "Replace:" in fallback_fix_comment
assert "Add:" in fallback_fix_comment
assert "Keep the repair limited" in fallback_fix_comment
assert "```suggestion" not in fallback_fix_comment
'''
if anchor not in selftest_text:
    raise SystemExit("expected config assertion anchor was not found in selftest")
selftest_text = selftest_text.replace(anchor, anchor + insert, 1)
selftest.write_text(selftest_text, encoding="utf-8")
'@
  $scriptPath = Join-Path $env:RUNNER_TEMP 'patch_dcoir_review_fix_synthesis.py'
  $editScript | Set-Content -LiteralPath $scriptPath -Encoding UTF8
  python $scriptPath
  if ($LASTEXITCODE -ne 0) { throw 'patch script failed' }

  python -m py_compile $basePath $runnerPath $selftestPath
  if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
  python $selftestPath
  if ($LASTEXITCODE -ne 0) { throw 'Pareto context selftest failed' }
  Invoke-Git @('diff', '--check', '--', $runnerPath, $selftestPath)

  & git diff --quiet -- $runnerPath $selftestPath
  $diffCode = $LASTEXITCODE
  if ($diffCode -eq 0) { throw 'patch produced no source changes' }
  if ($diffCode -ne 1) { throw "git diff failed with exit $diffCode" }

  $reportDir = Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $requestId
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $summaryPath = Join-Path $reportDir 'fix_synthesis_verifier_summary.md'
  @(
    '# DCOIR Review fix synthesis verifier update',
    '',
    "- branch: $branch",
    "- runner_path: $runnerPath",
    "- selftest_path: $selftestPath",
    '- change: native GitHub suggestions now require one verified replacement line anchored to the fetched PR-head file text',
    '- fallback: broader repairs stay as structured Remove / Replace / Add guidance',
    '- validation: python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py; python .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py; git diff --check'
  ) | Set-Content -LiteralPath $summaryPath -Encoding UTF8

  Invoke-Git @('add', '--', $runnerPath, $selftestPath)
  Invoke-Git @('commit', '-m', 'Verify dcoir review fix suggestions')
  $newHead = (& git rev-parse HEAD).Trim()
  Write-Host "New branch head: $newHead"
  Invoke-Git @('push', 'origin', "HEAD:refs/heads/$branch")
  Write-Host "Pushed $branch at $newHead"
}
finally {
  try {
    Invoke-Git @('fetch', '--no-tags', 'origin', 'main')
    Invoke-Git @('checkout', '-B', 'main', 'origin/main')
    Invoke-Git @('status', '--short')
  } catch {
    Write-Warning "Unable to restore workflow workspace to main: $_"
  }
}
