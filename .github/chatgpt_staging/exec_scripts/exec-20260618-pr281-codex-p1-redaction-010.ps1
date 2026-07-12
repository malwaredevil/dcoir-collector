$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ExpectedHead = "94759784627f546c3ae30b3a5521fc59a1925a50"
$PrBranch = "implement-pr-review-command-workflow"
$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1"
if (-not (Test-Path $sourceScript)) {
    throw "Expected source script not found: $sourceScript"
}

function Invoke-NativeChecked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        if ($output) {
            $output | Write-Output
        }
        throw "$Description failed with exit code $exitCode"
    }
    if ($output) {
        $output | Write-Output
    }
}

Invoke-NativeChecked "git fetch PR branch" { git fetch --quiet origin $PrBranch }
$currentHead = (git rev-parse FETCH_HEAD).Trim()
if ($currentHead -ne $ExpectedHead) {
    throw "Unexpected PR branch head. Expected $ExpectedHead but found $currentHead"
}

$workDir = Join-Path $env:RUNNER_TEMP "pr281-redaction-worktree"
if (Test-Path $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}
Invoke-NativeChecked "git worktree add PR head" { git worktree add --detach $workDir $ExpectedHead }

$postFixPath = Join-Path $env:RUNNER_TEMP "post-fix-pr281-codex-redaction.py"
$postFixScript = @'
from pathlib import Path

SCRIPT = Path(".github/dcoir_review/scripts/openrouter_pr_review.py")
REGRESSION = Path("scripts/openrouter_pr_review_codex_regression_selftest.py")

text = SCRIPT.read_text(encoding="utf-8")
bad_quote_branch = '''        if text[index] in {"\\\"", "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 1, text[index])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
'''
start = text.index("def find_unquoted_header_credential_end(text: str, start: int) -> int:")
end = text.index("\n\ndef find_unquoted_header_value_end(text: str, start: int) -> int:", start)
section = text[start:end]
if section.count(bad_quote_branch) != 1:
    raise SystemExit(f"header quote branch in header function: expected one match, found {section.count(bad_quote_branch)}")
section = section.replace(bad_quote_branch, "", 1)
text = text[:start] + section + text[end:]
SCRIPT.write_text(text, encoding="utf-8")

regression = '''#!/usr/bin/env python3
"""Focused regressions for External Codex PR #281 redaction findings."""

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
REDACTION = "[redacted-secret]"


def sanitized(text: str) -> str:
    return mod.sanitize_text(text, config)


def assert_redacted(source: str, *secret_fragments: str) -> None:
    cleaned = sanitized(source)
    for fragment in secret_fragments:
        assert fragment not in cleaned, cleaned
    assert REDACTION in cleaned, cleaned


unsafe_header = "Authorization: Bearer ${{ secrets.OPENROUTER_TOKEN || 'fallback header secret 12345' }}"
cleaned_header = sanitized(unsafe_header)
assert "fallback header secret 12345" not in cleaned_header, cleaned_header
assert "Authorization: Bearer [redacted-secret]" in cleaned_header, cleaned_header

assert_redacted(
    "Proxy-Authorization: Basic $(printf 'proxy fallback header secret 12345')",
    "proxy fallback header secret 12345",
)
assert_redacted(
    "X-Api-Key: `printf backtick header secret 12345`",
    "backtick header secret 12345",
)

line_continuation = chr(92) + chr(10)

curl_user_continuation = 'curl --user ' + line_continuation + '  "dcoir:continued curl secret 12345" https://example.test/'
cleaned_curl_user = sanitized(curl_user_continuation)
assert "continued curl secret 12345" not in cleaned_curl_user, cleaned_curl_user
assert "dcoir:[redacted-secret]" in cleaned_curl_user, cleaned_curl_user

curl_proxy_continuation = "curl --proxy-user " + line_continuation + "  'proxy:continued proxy secret 12345' https://example.test/"
cleaned_curl_proxy = sanitized(curl_proxy_continuation)
assert "continued proxy secret 12345" not in cleaned_curl_proxy, cleaned_curl_proxy
assert "proxy:[redacted-secret]" in cleaned_curl_proxy, cleaned_curl_proxy

curl_short_continuation = "curl -u" + line_continuation + "  dcoir:continued-short-option-secret-12345 https://example.test/"
cleaned_curl_short = sanitized(curl_short_continuation)
assert "continued-short-option-secret-12345" not in cleaned_curl_short, cleaned_curl_short
assert "dcoir:[redacted-secret]" in cleaned_curl_short, cleaned_curl_short

print("openrouter_pr_review_codex_regression_selftest.py: ok")
'''
REGRESSION.write_text(regression, encoding="utf-8")
'@
Set-Content -Path $postFixPath -Value $postFixScript -Encoding UTF8

$script = Get-Content -Path $sourceScript -Raw
$script = $script.Replace('$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"')
$script = $script.Replace('git fetch origin $PrBranch', 'git fetch --quiet origin $PrBranch')

$patchAnchor = 'Invoke-Checked "Patch script" { python $patcherPath }'
$postFixPathLiteral = $postFixPath.Replace("'", "''")
$postFixCall = "Invoke-Checked `"Post-patch redaction fix`" { python '$postFixPathLiteral' }"
if (-not $script.Contains($patchAnchor)) {
    throw "Patch anchor not found in source script"
}
$script = $script.Replace($patchAnchor, ($patchAnchor + "`n" + $postFixCall))

$commitAnchor = 'Invoke-Checked "git add" { git add .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_codex_regression_selftest.py }'
$gitIdentity = @'
Invoke-Checked "git configure user email" { git config user.email "chatgpt-exec@users.noreply.github.com" }
Invoke-Checked "git configure user name" { git config user.name "ChatGPT Exec" }
'@
if (-not $script.Contains($commitAnchor)) {
    throw "Commit anchor not found in source script"
}
$script = $script.Replace($commitAnchor, ($gitIdentity + $commitAnchor))

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260618-pr281-codex-p1-redaction-010-expanded.ps1"
Set-Content -Path $tempScript -Value $script -Encoding UTF8

Push-Location $workDir
try {
    & $tempScript
} finally {
    Pop-Location
}
