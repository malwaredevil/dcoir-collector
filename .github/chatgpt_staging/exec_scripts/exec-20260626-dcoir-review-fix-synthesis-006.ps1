$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$requestId = 'exec-20260626-dcoir-review-fix-synthesis-006'
$branch = 'fix/dcoir-review-fix-synthesis-verifier-20260626'
$runnerPath = '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py'
$selftestPath = '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py'
$basePath = '.github/dcoir_review/scripts/openrouter_pr_review.py'
$expectedRunnerBlob = '05ea1efa90dfa3f34e36b5c9dfd05a8861c5c16a'
$expectedSelftestBlob = 'f713c827409cd79817d91d9fe7d2a4d82e055f01'
$reportDir = Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $requestId
$summaryPath = Join-Path $reportDir 'fix_synthesis_verifier_summary.md'
$script:SummaryLines = New-Object System.Collections.Generic.List[string]
$script:BranchHead = ''
$script:Result = 'failure'
$script:Phase = 'start'
$script:CapturedError = $null

function Add-Summary {
  param([AllowNull()][string]$Line)
  if ($null -eq $Line) { $Line = '' }
  $script:SummaryLines.Add($Line) | Out-Null
  Write-Host $Line
}

function Set-Phase {
  param([string]$Name)
  $script:Phase = $Name
  Add-Summary "phase=$Name"
}

function Add-OutputLines {
  param([AllowNull()]$Output)
  if ($null -eq $Output) { return }
  $count = 0
  foreach ($item in $Output) {
    if ($count -ge 80) {
      Add-Summary '    [output truncated in summary]'
      break
    }
    $text = ($item | Out-String).TrimEnd()
    if (-not [string]::IsNullOrWhiteSpace($text)) {
      Add-Summary "    $text"
      $count += 1
    }
  }
}

function Invoke-Native {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string[]]$Arguments
  )
  $oldPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = & $FilePath @Arguments 2>&1
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $oldPreference
  }
  return [pscustomobject]@{ Code = $code; Output = $output }
}

function Invoke-Git {
  param([Parameter(Mandatory=$true)][string[]]$GitArgs)
  Add-Summary "git $($GitArgs -join ' ')"
  $result = Invoke-Native -FilePath 'git' -Arguments $GitArgs
  Add-OutputLines -Output $result.Output
  if ([int]$result.Code -ne 0) { throw "git failed with exit $($result.Code)`: git $($GitArgs -join ' ')" }
}

function Invoke-Python {
  param([Parameter(Mandatory=$true)][string[]]$PythonArgs)
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    $cmd = $python.Source
    $displayArgs = $PythonArgs
  } else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { throw 'Neither python nor py is available on the runner PATH' }
    $cmd = $py.Source
    $displayArgs = @('-3') + $PythonArgs
  }
  Add-Summary "python $($displayArgs -join ' ')"
  $result = Invoke-Native -FilePath $cmd -Arguments $displayArgs
  Add-OutputLines -Output $result.Output
  if ([int]$result.Code -ne 0) { throw "python failed with exit $($result.Code)`: $($displayArgs -join ' ')" }
}

function Get-TrackedBlob {
  param([string]$Path)
  $result = Invoke-Native -FilePath 'git' -Arguments @('ls-files', '-s', '--', $Path)
  if ([int]$result.Code -ne 0) {
    Add-OutputLines -Output $result.Output
    throw "Unable to read tracked blob for $Path"
  }
  $lineText = ($result.Output | Select-Object -First 1 | Out-String).Trim()
  if ([string]::IsNullOrWhiteSpace($lineText)) { throw "No tracked blob entry for $Path" }
  return (($lineText -split '\s+')[1])
}

function Assert-Blob {
  param([string]$Path, [string]$Expected)
  $actual = Get-TrackedBlob -Path $Path
  Add-Summary "$Path blob=$actual"
  if ($actual -ne $Expected) { throw "Blob mismatch for $Path expected $Expected got $actual" }
}

function Write-ExecSummary {
  param([string]$Result, [string]$ErrorText)
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $head = ''
  try {
    $headResult = Invoke-Native -FilePath 'git' -Arguments @('rev-parse', 'HEAD')
    if ([int]$headResult.Code -eq 0) { $head = ($headResult.Output | Select-Object -First 1 | Out-String).Trim() }
  } catch { $head = '' }
  $lines = New-Object System.Collections.Generic.List[string]
  foreach ($line in @(
    '# DCOIR Review fix synthesis verifier update',
    '',
    "- request_id: $requestId",
    "- result: $Result",
    "- phase: $script:Phase",
    "- branch: $branch",
    "- branch_head: $script:BranchHead",
    "- workspace_head_after_restore: $head",
    "- runner_path: $runnerPath",
    "- selftest_path: $selftestPath",
    '- change: native GitHub suggestions require one verified replacement line anchored to the fetched PR-head file text',
    '- fallback: broader repairs remain structured Remove / Replace / Add guidance',
    '- validation: python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py; python .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py; git diff --check'
  )) { $lines.Add($line) | Out-Null }
  if (-not [string]::IsNullOrWhiteSpace($ErrorText)) {
    $lines.Add('') | Out-Null
    $lines.Add('## Error') | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('```text') | Out-Null
    foreach ($errorLine in (($ErrorText -replace "`r", '') -split "`n" | Select-Object -First 100)) {
      $lines.Add($errorLine) | Out-Null
    }
    $lines.Add('```') | Out-Null
  }
  $lines.Add('') | Out-Null
  $lines.Add('## Timeline') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($entry in $script:SummaryLines) { $lines.Add($entry) | Out-Null }
  $lines | Set-Content -LiteralPath $summaryPath -Encoding UTF8
}

try {
  Add-Summary "request=$requestId"
  Set-Phase 'fetch-main'
  Invoke-Git -GitArgs @('fetch', '--no-tags', 'origin', 'main')

  Set-Phase 'checkout-branch'
  Invoke-Git -GitArgs @('checkout', '-B', $branch, 'origin/main')
  Invoke-Git -GitArgs @('config', 'user.name', 'github-actions[bot]')
  Invoke-Git -GitArgs @('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')

  Set-Phase 'assert-source-blobs'
  Assert-Blob -Path $runnerPath -Expected $expectedRunnerBlob
  Assert-Blob -Path $selftestPath -Expected $expectedSelftestBlob

  Set-Phase 'write-patch-script'
  $editScript = @'
from pathlib import Path

runner = Path(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py")
selftest = Path(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py")


def to_lf(text: str) -> tuple[str, str]:
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n"), newline


def write_preserving_newline(path: Path, text_lf: str, newline: str) -> None:
    path.write_text(text_lf.replace("\n", newline), encoding="utf-8", newline="")

runner_text, runner_newline = to_lf(runner.read_text(encoding="utf-8"))
old_verifier = r'''def verified_suggested_replacement(fix_result: dict[str, Any], line_text: str, config: Any) -> str:
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
new_verifier = r'''def verified_suggested_replacement(fix_result: dict[str, Any], file_text: str, line_number: int, config: Any) -> str:
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
write_preserving_newline(runner, runner_text, runner_newline)

selftest_text, selftest_newline = to_lf(selftest.read_text(encoding="utf-8"))
marker = 'fix_synthesis_verifier_marker = "single-line-pr-head-anchor"'
if marker in selftest_text:
    raise SystemExit("fix-synthesis verifier selftest block is already present")
anchor = "assert config.required_finding_min_per_family == 2\n"
insert = r'''

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
write_preserving_newline(selftest, selftest_text, selftest_newline)
'@
  $patchScriptPath = Join-Path $env:RUNNER_TEMP 'patch_dcoir_review_fix_synthesis.py'
  $editScript | Set-Content -LiteralPath $patchScriptPath -Encoding UTF8

  Set-Phase 'apply-patch'
  Invoke-Python -PythonArgs @($patchScriptPath)

  Set-Phase 'py-compile'
  Invoke-Python -PythonArgs @('-m', 'py_compile', $basePath, $runnerPath, $selftestPath)

  Set-Phase 'selftest'
  Invoke-Python -PythonArgs @($selftestPath)

  Set-Phase 'diff-check'
  Invoke-Git -GitArgs @('diff', '--check', '--', $runnerPath, $selftestPath)
  Add-Summary 'git diff --stat'
  $diffStat = Invoke-Native -FilePath 'git' -Arguments @('diff', '--stat', '--', $runnerPath, $selftestPath)
  Add-OutputLines -Output $diffStat.Output
  if ([int]$diffStat.Code -ne 0) { throw "git diff --stat failed with exit $($diffStat.Code)" }

  Set-Phase 'ensure-diff'
  $diffQuiet = Invoke-Native -FilePath 'git' -Arguments @('diff', '--quiet', '--', $runnerPath, $selftestPath)
  if ([int]$diffQuiet.Code -eq 0) { throw 'patch produced no source changes' }
  if ([int]$diffQuiet.Code -ne 1) {
    Add-OutputLines -Output $diffQuiet.Output
    throw "git diff failed with exit $($diffQuiet.Code)"
  }

  Set-Phase 'commit-branch'
  Invoke-Git -GitArgs @('add', '--', $runnerPath, $selftestPath)
  Invoke-Git -GitArgs @('commit', '-m', 'Verify dcoir review fix suggestions')
  $headResult = Invoke-Native -FilePath 'git' -Arguments @('rev-parse', 'HEAD')
  if ([int]$headResult.Code -ne 0) { throw 'unable to read new branch head' }
  $script:BranchHead = ($headResult.Output | Select-Object -First 1 | Out-String).Trim()
  Add-Summary "new_branch_head=$script:BranchHead"

  Set-Phase 'push-branch'
  Invoke-Git -GitArgs @('push', 'origin', "HEAD:refs/heads/$branch")
  $script:Result = 'success'
  Set-Phase 'pushed'
}
catch {
  $script:CapturedError = $_
  Add-Summary "ERROR: $($_ | Out-String)"
}
finally {
  try {
    Add-Summary 'restore workspace to origin/main'
    Invoke-Git -GitArgs @('fetch', '--no-tags', 'origin', 'main')
    Invoke-Git -GitArgs @('checkout', '-B', 'main', 'origin/main')
    Invoke-Git -GitArgs @('status', '--short')
  } catch {
    Add-Summary "WARNING: Unable to restore workflow workspace to main: $($_ | Out-String)"
  }
  $errorText = ''
  if ($null -ne $script:CapturedError) { $errorText = ($script:CapturedError | Out-String) }
  Write-ExecSummary -Result $script:Result -ErrorText $errorText
}

if ($null -ne $script:CapturedError) {
  throw $script:CapturedError
}
