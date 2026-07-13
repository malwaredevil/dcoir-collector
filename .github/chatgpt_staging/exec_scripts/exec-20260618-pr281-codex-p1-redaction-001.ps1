$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo) -or -not (Test-Path -LiteralPath $repo -PathType Container)) { throw 'Unable to resolve repository root.' }

$branch = 'implement-pr-review-command-workflow'
$expectedHead = '94759784627f546c3ae30b3a5521fc59a1925a50'
$requestId = 'exec-20260618-pr281-codex-p1-redaction-001'
$fetchRefspec = "+refs/heads/${branch}:refs/remotes/origin/${branch}"
$pushRefspec = "HEAD:refs/heads/${branch}"
$tempRoot = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($tempRoot)) { $tempRoot = [IO.Path]::GetTempPath() }
$worktree = Join-Path $tempRoot $requestId
$patchScript = Join-Path $tempRoot "$requestId.py"
$expectedBlobs = @{
    '.github/dcoir_review/scripts/openrouter_pr_review.py' = '364e21a26d966b89b3439c534fd59990c32139b6'
}
$expectedPaths = @(
    '.github/dcoir_review/scripts/openrouter_pr_review.py',
    'scripts/openrouter_pr_review_codex_regression_selftest.py'
)
$validationResults = New-Object System.Collections.Generic.List[string]

function Invoke-Git {
    param([Parameter(Mandatory=$true)][string]$Cwd, [Parameter(Mandatory=$true)][string[]]$GitArgs)
    $old = $ErrorActionPreference; $output = @(); $exitCode = $null
    try { $ErrorActionPreference = 'Continue'; $output = & git -C $Cwd @GitArgs 2>&1; $exitCode = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($exitCode -ne 0) { throw "git $($GitArgs -join ' ') failed with exit code $exitCode`n$output" }
    return $output
}

function Invoke-NativeCommand {
    param([Parameter(Mandatory=$true)][string]$FilePath, [Parameter(Mandatory=$true)][string[]]$Arguments, [Parameter(Mandatory=$true)][string]$Description)
    $old = $ErrorActionPreference; $output = @(); $exitCode = $null
    try { $ErrorActionPreference = 'Continue'; $output = & $FilePath @Arguments 2>&1; $exitCode = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($exitCode -ne 0) { throw "$Description failed with exit code $exitCode`n$output" }
    return $output
}

function Get-GitText {
    param([string]$Cwd, [string[]]$GitArgs)
    return ((Invoke-Git -Cwd $Cwd -GitArgs $GitArgs | Out-String).Trim())
}

function Get-TrackedBlob {
    param([string]$Cwd, [string]$Path)
    $line = Get-GitText -Cwd $Cwd -GitArgs @('ls-files','-s','--',$Path)
    if ([string]::IsNullOrWhiteSpace($line)) { return '' }
    return (($line -split '\s+')[1])
}

function Get-RequiredGitToken {
    foreach ($name in @('DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($value)) { $value = [Environment]::GetEnvironmentVariable($name, 'Machine') }
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Write-Host "Using bridged GitHub token secret for PR branch push: $name"
            Write-Host "::add-mask::$value"
            return $value
        }
    }
    throw 'No bridged GitHub token secret is available for PR branch push.'
}

function Invoke-GitPushWithToken {
    param([string]$Cwd, [string]$Token, [string]$Refspec)
    $repoFull = $env:GITHUB_REPOSITORY
    if ([string]::IsNullOrWhiteSpace($repoFull)) { $repoFull = 'DCOIR-Collector/dcoir-collector' }
    $pushUrl = "https://x-access-token:${Token}@github.com/${repoFull}.git"
    $old = $ErrorActionPreference; $output = @(); $exitCode = $null
    try { $ErrorActionPreference = 'Continue'; $output = & git -C $Cwd -c 'http.https://github.com/.extraheader=' push $pushUrl $Refspec 2>&1; $exitCode = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($exitCode -ne 0) { $safeOutput = (($output | Out-String).Replace($Token, '[REDACTED:GITHUB_TOKEN]')).Trim(); throw "git push failed with exit code $exitCode`n$safeOutput" }
    return $output
}

Invoke-Git -Cwd $repo -GitArgs @('fetch','origin',$fetchRefspec) | Out-Null
$remoteHead = Get-GitText -Cwd $repo -GitArgs @('rev-parse',"origin/$branch")
if ($remoteHead -ne $expectedHead) { throw "PR branch head mismatch. Expected $expectedHead but origin/$branch is $remoteHead." }

if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }
Invoke-Git -Cwd $repo -GitArgs @('worktree','prune') | Out-Null
Invoke-Git -Cwd $repo -GitArgs @('worktree','add','--detach',$worktree,"origin/$branch") | Out-Null

try {
    foreach ($path in $expectedBlobs.Keys) {
        $actualBlob = Get-TrackedBlob -Cwd $worktree -Path $path
        if ($actualBlob -ne $expectedBlobs[$path]) { throw "Blob mismatch before patch for $path. Expected $($expectedBlobs[$path]) but got $actualBlob." }
    }

    $pythonPatch = @'
from pathlib import Path
import sys

repo = Path(sys.argv[1])
review_path = repo / ".github/dcoir_review/scripts/openrouter_pr_review.py"
regression_path = repo / "scripts/openrouter_pr_review_codex_regression_selftest.py"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)

text = read(review_path)

header_block_start = text.index("HEADER_CREDENTIAL = re.compile(")
header_block_end = text.index("HEADER_FIELD_CREDENTIAL_START = re.compile(", header_block_start)
value_start = text.index("(?P<value>", header_block_start, header_block_end)
value_end = text.index(")(?P=quote)", value_start, header_block_end) + len(")(?P=quote)")
old_value = text[value_start:value_end]
if "[^$`" not in old_value:
    if not old_value.startswith("(?P<value>[^"):
        raise SystemExit(f"unexpected HEADER_CREDENTIAL value pattern: {old_value}")
    text = text[:value_start] + old_value.replace("(?P<value>[^", "(?P<value>[^$`", 1) + text[value_end:]

if "UNQUOTED_HEADER_CREDENTIAL_START" not in text:
    text = text.replace(
        "HEADER_FIELD_CREDENTIAL_START = re.compile(\n",
        """UNQUOTED_HEADER_CREDENTIAL_START = re.compile(
    r\"\"\"(?ix)(?<![A-Z0-9_\\-])(?P<name_quote>[\\\"']?)(?P<name>(?:proxy-)?authorization|x-api-key|api-key|x-auth-token|x-access-token)(?P=name_quote)(?P<sep>\\s*[:=]\\s*)(?:(?P<scheme>bearer|basic|token)\\s+)?(?![\\\"'])\"\"\"
)
HEADER_FIELD_CREDENTIAL_START = re.compile(
""",
        1,
    )

if "def redact_unquoted_header_credentials" not in text:
    text = text.replace(
        "def is_inline_object_cookie_context(text: str, field_start: int) -> bool:\n",
        """def redact_unquoted_header_credentials(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in UNQUOTED_HEADER_CREDENTIAL_START.finditer(text):
        if match.start() < cursor:
            continue
        value_start = match.end()
        if value_start >= len(text):
            continue
        value_end = find_unquoted_curl_credential_end(text, value_start)
        value = text[value_start:value_end].strip()
        if not value:
            continue
        result.append(text[cursor:value_start])
        if value == REDACTION or is_safe_reference(value):
            result.append(text[value_start:value_end])
        else:
            result.append(REDACTION)
        cursor = value_end
    if not result:
        return text
    result.append(text[cursor:])
    return \"\".join(result)


def is_inline_object_cookie_context(text: str, field_start: int) -> bool:
""",
        1,
    )

if "def skip_curl_line_continuation_whitespace" not in text:
    text = text.replace(
        "def redact_curl_user_credentials(text: str) -> str:\n",
        """def skip_curl_line_continuation_whitespace(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text[index] != \"\\\\\":
            return index
        next_index = index + 1
        if next_index < len(text) and text[next_index] == \"\\r\":
            next_index += 1
            if next_index < len(text) and text[next_index] == \"\\n\":
                next_index += 1
        elif next_index < len(text) and text[next_index] == \"\\n\":
            next_index += 1
        else:
            return index
        index = next_index
        while index < len(text) and text[index] in {\" \", \"\\t\"}:
            index += 1
    return index


def redact_curl_user_credentials(text: str) -> str:
""",
        1,
    )

text = replace_once(
    text,
    "        value_start = match.end()\n        if value_start >= len(text):\n",
    "        value_start = skip_curl_line_continuation_whitespace(text, match.end())\n        if value_start >= len(text):\n",
    "curl value_start",
)

text = replace_once(
    text,
    "    cleaned = redact_unquoted_cookie_credentials(cleaned)\n    cleaned = HEADER_CREDENTIAL.sub(redact_header_credential, cleaned)\n",
    "    cleaned = redact_unquoted_cookie_credentials(cleaned)\n    cleaned = redact_unquoted_header_credentials(cleaned)\n    cleaned = HEADER_CREDENTIAL.sub(redact_header_credential, cleaned)\n",
    "sanitize_text header scanner insertion",
)

for needle in [
    "UNQUOTED_HEADER_CREDENTIAL_START",
    "def redact_unquoted_header_credentials",
    "def skip_curl_line_continuation_whitespace",
    "cleaned = redact_unquoted_header_credentials(cleaned)",
]:
    if needle not in text:
        raise SystemExit(f"post-patch missing {needle}")

write(review_path, text)

regression = r'''#!/usr/bin/env python3
"""Focused regressions for Codex-reviewed OpenRouter redaction gaps."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

config = mod.load_yaml_like_config(str(ROOT / ".github" / "openrouter-pr-review.yml"))

header_fallback = "fallback header secret 12345"
proxy_header_fallback = "proxy fallback header secret 12345"
backtick_header = "backtick header secret 12345"
curl_continuation = "line continuation curl secret 12345!"
proxy_curl_continuation = "line continuation proxy secret 12345!"

cases = {
    f"Authorization: Bearer ${{{{ secrets.TOKEN || '{header_fallback}' }}}}": "Authorization: Bearer [redacted-secret]",
    f"Proxy-Authorization: Basic $(printf '{proxy_header_fallback}')": "Proxy-Authorization: Basic [redacted-secret]",
    f"Authorization: Bearer `printf {backtick_header}`": "Authorization: Bearer [redacted-secret]",
    f'curl --user \\\n  "dcoir:{curl_continuation}" https://example.test/': 'curl --user \\\n  "dcoir:[redacted-secret]" https://example.test/',
    f"curl --proxy-user \\\n  'proxy:{proxy_curl_continuation}' https://example.test/": "curl --proxy-user \\\n  'proxy:[redacted-secret]' https://example.test/",
    f"curl -u\\\n  dcoir:{curl_continuation} https://example.test/": "curl -u\\\n  dcoir:[redacted-secret] https://example.test/",
}

for raw, expected in cases.items():
    actual = mod.sanitize_text(raw, config)
    assert actual == expected, f"redaction mismatch\nraw={raw!r}\nexpected={expected!r}\nactual={actual!r}"

safe_header = "Authorization: Bearer ${{ secrets.OPENROUTER_TOKEN }}"
assert mod.sanitize_text(safe_header, config) == safe_header

combined = "\n".join(cases.keys())
cleaned = mod.sanitize_github_output(combined, config)
for leaked in [
    header_fallback,
    proxy_header_fallback,
    backtick_header,
    curl_continuation,
    proxy_curl_continuation,
]:
    assert leaked not in cleaned, cleaned
assert "[redacted-secret]" in cleaned

print("codex redaction regression selftest passed")
'''
write(regression_path, regression)
'@
    [System.IO.File]::WriteAllText($patchScript, $pythonPatch, (New-Object System.Text.UTF8Encoding($false)))
    Invoke-NativeCommand -FilePath 'python' -Arguments @($patchScript, $worktree) -Description 'Patch script' | Out-Null
    $validationResults.Add('patch_script: pass') | Out-Null

    Invoke-NativeCommand -FilePath 'python' -Arguments @('-m','py_compile', (Join-Path $worktree '.github/dcoir_review/scripts/openrouter_pr_review.py'), (Join-Path $worktree 'scripts/openrouter_pr_review_selftest.py'), (Join-Path $worktree 'scripts/openrouter_pr_review_codex_regression_selftest.py')) -Description 'py_compile OpenRouter review scripts' | Out-Null
    $validationResults.Add('py_compile_openrouter_scripts: pass') | Out-Null

    Invoke-NativeCommand -FilePath 'python' -Arguments @((Join-Path $worktree 'scripts/openrouter_pr_review_selftest.py')) -Description 'existing OpenRouter offline selftest' | Out-Null
    $validationResults.Add('existing_openrouter_selftest: pass') | Out-Null

    Invoke-NativeCommand -FilePath 'python' -Arguments @((Join-Path $worktree 'scripts/openrouter_pr_review_codex_regression_selftest.py')) -Description 'Codex redaction regression selftest' | Out-Null
    $validationResults.Add('codex_redaction_regression_selftest: pass') | Out-Null

    Invoke-Git -Cwd $worktree -GitArgs @('diff','--check','--') | Out-Null
    $validationResults.Add('git_diff_check: pass') | Out-Null

    Invoke-Git -Cwd $worktree -GitArgs @('config','user.name','github-actions[bot]') | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs @('config','user.email','41898282+github-actions[bot]@users.noreply.github.com') | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs (@('add','--') + $expectedPaths) | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs @('diff','--cached','--check') | Out-Null
    $validationResults.Add('git_diff_cached_check: pass') | Out-Null

    $changedNames = Get-GitText -Cwd $worktree -GitArgs @('diff','--cached','--name-only')
    $actualPaths = @($changedNames -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $unexpected = @($actualPaths | Where-Object { $expectedPaths -notcontains $_ })
    $missing = @($expectedPaths | Where-Object { $actualPaths -notcontains $_ })
    if ($unexpected.Count -gt 0) { throw "Unexpected changed paths: $($unexpected -join ', ')" }
    if ($missing.Count -gt 0) { throw "Missing expected changed paths: $($missing -join ', ')" }

    Invoke-Git -Cwd $worktree -GitArgs @('commit','-m','Fix OpenRouter redaction review gaps') | Out-Null
    $newHead = Get-GitText -Cwd $worktree -GitArgs @('rev-parse','HEAD')
    $token = Get-RequiredGitToken
    Invoke-GitPushWithToken -Cwd $worktree -Token $token -Refspec $pushRefspec | Out-Null

    $reportDir = Join-Path $repo (Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $requestId)
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    $summaryPath = Join-Path $reportDir 'pr281_redaction_summary.md'
    @(
        '# PR 281 redaction fix summary',
        '',
        "- previous_head: $expectedHead",
        "- new_head: $newHead",
        '- branch: implement-pr-review-command-workflow',
        '- changed_paths:',
        '  - .github/dcoir_review/scripts/openrouter_pr_review.py',
        '  - scripts/openrouter_pr_review_codex_regression_selftest.py',
        '- addressed_external_codex_threads:',
        '  - PRRT_kwDOR0OHZ86Kri2H / redact entire unquoted header expressions',
        '  - PRRT_kwDOR0OHZ86Kri2L / handle line continuations before curl credentials',
        '- validation:',
        ($validationResults | ForEach-Object { "  - $_" })
    ) | Out-File -FilePath $summaryPath -Encoding utf8

    Write-Host "PR branch updated to $newHead"
    Write-Host "Validation results:"
    $validationResults | ForEach-Object { Write-Host "- $_" }
}
finally {
    try { Invoke-Git -Cwd $repo -GitArgs @('worktree','remove','--force',$worktree) | Out-Null } catch { Write-Warning "Unable to remove temp worktree: $worktree" }
}
