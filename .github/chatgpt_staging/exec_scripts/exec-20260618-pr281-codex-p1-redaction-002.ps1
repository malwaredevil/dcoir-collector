$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ExpectedHead = "94759784627f546c3ae30b3a5521fc59a1925a50"
$ExpectedScriptBlob = "364e21a26d966b89b3439c534fd59990c32139b6"
$PrBranch = "implement-pr-review-command-workflow"

function Invoke-Checked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    $output = & $Command 2>&1
    $exitCode = $LASTEXITCODE
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

Invoke-Checked "git fetch PR branch" { git fetch origin $PrBranch }
$currentHead = (git rev-parse FETCH_HEAD).Trim()
if ($currentHead -ne $ExpectedHead) {
    throw "Unexpected PR branch head. Expected $ExpectedHead but found $currentHead"
}

Invoke-Checked "git switch to expected PR head" { git switch --detach $ExpectedHead }
$treeSpec = "${ExpectedHead}:.github/dcoir_review/scripts/openrouter_pr_review.py"
$currentScriptBlob = (git rev-parse $treeSpec).Trim()
if ($currentScriptBlob -ne $ExpectedScriptBlob) {
    throw "Unexpected .github/dcoir_review/scripts/openrouter_pr_review.py blob. Expected $ExpectedScriptBlob but found $currentScriptBlob"
}

$patcherPath = Join-Path $env:RUNNER_TEMP "patch-pr281-codex-redaction.py"
$patcher = @'
from pathlib import Path

SCRIPT = Path(".github/dcoir_review/scripts/openrouter_pr_review.py")
REGRESSION = Path("scripts/openrouter_pr_review_codex_regression_selftest.py")
REDACTION = "[redacted-secret]"

text = SCRIPT.read_text(encoding="utf-8")

old_value_fragment = "(?P<value>[^\\\"'\\s,;)}\\r\\n]+)(?P=quote)"
new_value_fragment = "(?P<value>(?![$`])[^\\\"'\\s,;)}\\r\\n]+)(?P=quote)"
if text.count(old_value_fragment) != 1:
    raise SystemExit(f"header value fragment: expected one match, found {text.count(old_value_fragment)}")
text = text.replace(old_value_fragment, new_value_fragment, 1)

if "UNQUOTED_HEADER_CREDENTIAL_START" not in text:
    insert_before = "\nCOOKIE_UNQUOTED_FIELD_START = re.compile(\n"
    new_constant = """
UNQUOTED_HEADER_CREDENTIAL_START = re.compile(
    r\"\"\"(?ix)(?<![A-Z0-9_\\-])(?P<name_quote>[\\\"']?)(?P<name>(?:proxy-)?authorization|x-api-key|api-key|x-auth-token|x-access-token)(?P=name_quote)(?P<sep>\\s*[:=]\\s*)(?!\\s*[\\\"'])\"\"\"
)
"""
    if text.count(insert_before) != 1:
        raise SystemExit("unquoted header constant insertion anchor not found once")
    text = text.replace(insert_before, "\n" + new_constant + insert_before, 1)

if "def find_unquoted_header_credential_end" not in text:
    insert_before = "\n\ndef redact_header_field_credentials(text: str) -> str:\n"
    new_functions = '''

def find_unquoted_header_credential_end(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text.startswith("${{", index):
            expression_end = find_github_expression_end(text, index + 3)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end
            continue
        if text.startswith("${", index):
            expression_end = text.find("}", index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text.startswith("$(", index):
            expression_end = find_command_substitution_end(text, index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "$" and index + 1 < len(text) and text[index + 1] in {"\\\"", "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 2, text[index + 1])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] == "`":
            expression_end = find_backtick_substitution_end(text, index + 1)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "\\\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] in {"\\\"", "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 1, text[index])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] in {"\\r", "\\n", "\\t", " ", "\\\"", "'", ",", ";", ")", "}", "]"}:
            return index
        index += 1
    return index


def find_unquoted_header_value_end(text: str, start: int) -> int:
    probe = start
    while probe < len(text) and text[probe] in {" ", "\\t"}:
        probe += 1
    for scheme in ("bearer", "basic", "token"):
        scheme_end = probe + len(scheme)
        if text[probe:scheme_end].lower() == scheme and scheme_end < len(text) and text[scheme_end] in {" ", "\\t"}:
            secret_start = scheme_end
            while secret_start < len(text) and text[secret_start] in {" ", "\\t"}:
                secret_start += 1
            return find_unquoted_header_credential_end(text, secret_start)
    return find_unquoted_header_credential_end(text, start)


def redact_unquoted_header_credentials(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in UNQUOTED_HEADER_CREDENTIAL_START.finditer(text):
        if match.start() < cursor:
            continue
        value_start = match.end()
        value_end = find_unquoted_header_value_end(text, value_start)
        value = text[value_start:value_end]
        stripped_value = value.strip()
        if not stripped_value or stripped_value == REDACTION:
            continue
        scheme_match = HEADER_VALUE_SCHEME.fullmatch(value)
        secret_value = scheme_match.group("secret").strip() if scheme_match else stripped_value
        if is_safe_reference(stripped_value) or (scheme_match and is_safe_reference(secret_value)):
            continue
        result.append(text[cursor:value_start])
        if scheme_match:
            result.append(f"{scheme_match.group('prefix')}{REDACTION}")
        else:
            leading = value[: len(value) - len(value.lstrip())]
            result.append(f"{leading}{REDACTION}")
        cursor = value_end
    if not result:
        return text
    result.append(text[cursor:])
    return "".join(result)
'''
    if text.count(insert_before) != 1:
        raise SystemExit("unquoted header function insertion anchor not found once")
    text = text.replace(insert_before, new_functions + insert_before, 1)

if "def skip_curl_line_continuation_whitespace" not in text:
    insert_before = "\n\ndef redact_curl_user_credentials(text: str) -> str:\n"
    new_function = '''

def skip_curl_line_continuation_whitespace(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text[index] != "\\\\":
            return index
        if index + 2 < len(text) and text[index + 1] == "\\r" and text[index + 2] == "\\n":
            index += 3
        elif index + 1 < len(text) and text[index + 1] in {"\\r", "\\n"}:
            index += 2
        else:
            return index
        while index < len(text) and text[index] in {" ", "\\t"}:
            index += 1
    return index
'''
    if text.count(insert_before) != 1:
        raise SystemExit("curl continuation helper insertion anchor not found once")
    text = text.replace(insert_before, new_function + insert_before, 1)

curl_function_start = text.index("def redact_curl_user_credentials(text: str) -> str:")
curl_before = text[:curl_function_start]
curl_after = text[curl_function_start:]
old_curl_start = "        value_start = match.end()\n        if value_start >= len(text):\n"
new_curl_start = "        value_start = skip_curl_line_continuation_whitespace(text, match.end())\n        if value_start >= len(text):\n"
if curl_after.count(old_curl_start) != 1:
    raise SystemExit(f"curl value_start in curl function: expected one match, found {curl_after.count(old_curl_start)}")
text = curl_before + curl_after.replace(old_curl_start, new_curl_start, 1)

sanitize_anchor = "    cleaned = redact_unquoted_cookie_credentials(cleaned)\n"
sanitize_replacement = "    cleaned = redact_unquoted_cookie_credentials(cleaned)\n    cleaned = redact_unquoted_header_credentials(cleaned)\n"
if sanitize_replacement not in text:
    if text.count(sanitize_anchor) != 1:
        raise SystemExit("sanitize insertion anchor not found once")
    text = text.replace(sanitize_anchor, sanitize_replacement, 1)

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

safe_header = "Authorization: Bearer ${{ secrets.OPENROUTER_TOKEN }}"
assert sanitized(safe_header) == safe_header

assert_redacted(
    "Proxy-Authorization: Basic $(printf 'proxy fallback header secret 12345')",
    "proxy fallback header secret 12345",
)
assert_redacted(
    "X-Api-Key: `printf backtick header secret 12345`",
    "backtick header secret 12345",
)

curl_user_continuation = "curl --user " + "\\" + "\n  \"dcoir:continued curl secret 12345\" https://example.test/"
cleaned_curl_user = sanitized(curl_user_continuation)
assert "continued curl secret 12345" not in cleaned_curl_user, cleaned_curl_user
assert "dcoir:[redacted-secret]" in cleaned_curl_user, cleaned_curl_user

curl_proxy_continuation = "curl --proxy-user " + "\\" + "\n  'proxy:continued proxy secret 12345' https://example.test/"
cleaned_curl_proxy = sanitized(curl_proxy_continuation)
assert "continued proxy secret 12345" not in cleaned_curl_proxy, cleaned_curl_proxy
assert "proxy:[redacted-secret]" in cleaned_curl_proxy, cleaned_curl_proxy

curl_short_continuation = "curl -u" + "\\" + "\n  dcoir:continued-short-option-secret-12345 https://example.test/"
cleaned_curl_short = sanitized(curl_short_continuation)
assert "continued-short-option-secret-12345" not in cleaned_curl_short, cleaned_curl_short
assert "dcoir:[redacted-secret]" in cleaned_curl_short, cleaned_curl_short

print("openrouter_pr_review_codex_regression_selftest.py: ok")
'''
REGRESSION.write_text(regression, encoding="utf-8")
'@
Set-Content -Path $patcherPath -Value $patcher -Encoding UTF8
Invoke-Checked "Patch script" { python $patcherPath }

Invoke-Checked "py_compile OpenRouter review scripts" { python -m py_compile .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_selftest.py scripts/openrouter_pr_review_codex_regression_selftest.py }
Invoke-Checked "existing OpenRouter selftest" { python scripts/openrouter_pr_review_selftest.py }
Invoke-Checked "Codex redaction regression selftest" { python scripts/openrouter_pr_review_codex_regression_selftest.py }
Invoke-Checked "git diff check" { git diff --check }

$changes = (git status --short)
if (-not $changes) {
    throw "Patch produced no changes"
}
$changes | Write-Output

Invoke-Checked "git add" { git add .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_codex_regression_selftest.py }
Invoke-Checked "git commit" { git commit -m "Fix OpenRouter redaction review gaps" }
Invoke-Checked "git push" { git push origin HEAD:$PrBranch }
$newHead = (git rev-parse HEAD).Trim()
Write-Output "Pushed PR branch $PrBranch at $newHead"
