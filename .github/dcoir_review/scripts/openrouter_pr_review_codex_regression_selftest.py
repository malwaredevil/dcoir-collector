#!/usr/bin/env python3
"""Focused regressions for External Codex PR #281 redaction findings."""

from __future__ import annotations

import ast
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

python_env_context = '''    return {
        "github_token": os.environ.get("GITHUB_TOKEN", ""),
        "openrouter_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "all_environment": "\\n".join(f"{key}={value}" for key, value in sorted(os.environ.items())),
    }
'''
cleaned_python_env_context = sanitized(python_env_context)
assert '"github_token": os.environ.get("GITHUB_TOKEN", ""),' in cleaned_python_env_context, cleaned_python_env_context
assert '"openrouter_key": os.environ.get("OPENROUTER_API_KEY", ""),' in cleaned_python_env_context, cleaned_python_env_context
assert '"github_token": [redacted-secret]' not in cleaned_python_env_context, cleaned_python_env_context
ast.parse("import os\n\ndef build_review_context():\n" + cleaned_python_env_context)

print("openrouter_pr_review_codex_regression_selftest.py: ok")
