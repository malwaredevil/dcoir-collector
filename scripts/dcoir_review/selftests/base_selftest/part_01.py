#!/usr/bin/env python3
"""Offline smoke checks for the DCOIR Review package."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review.py")
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

sample_diff = """diff --git a/calculator.js b/calculator.js
index 1111111..2222222 100644
--- a/calculator.js
+++ b/calculator.js
@@ -1,3 +1,4 @@
 function calculateTotal(price) {
+  const tax = 0.05;
   return price;
 }
"""

line_index = mod.build_diff_line_index(sample_diff)
assert ("calculator.js", 2) in line_index, line_index

config = mod.load_yaml_like_config(str(ROOT / ".github" / "openrouter-pr-review.yml"))
assert "/or-review" in config.commands
assert "/dcoir-review" in config.commands
assert config.model == "openrouter/free"
assert config.model_stack == ["openrouter/free"]
assert config.allowed_authors == ["malwaredevil"]
assert config.post_summary_when_findings is False
assert config.include_confidence is False
assert config.redact_secret_literals is True
assert config.openrouter_max_attempts == 4
assert config.openrouter_retry_max_seconds == 45
assert config.script_timeout_seconds == 1500
assert config.post_progress_comment is False
assert config.debug is False
assert config.ignored_providers == []
assert mod.provider_slug("Venice") == "venice"
assert mod.command_matches("/or-review", config.commands)
assert mod.command_matches("/or-review security", config.commands)
assert mod.command_matches("  /or-review security", config.commands)
assert mod.command_matches("\n/dcoir-review\tplease", config.commands)
assert mod.command_matches("/dcoir-review", config.commands)
assert mod.matching_command("/dcoir-review please", config.commands) == "/dcoir-review"
assert mod.command_requests_debug("/dcoir-review debug", "/dcoir-review")
assert mod.command_requests_debug("/dcoir-review debug=true", "/dcoir-review")
assert mod.command_requests_debug("/dcoir-review --debug", "/dcoir-review")
assert mod.command_requests_debug("/dcoir-review debug: true", "/dcoir-review")
assert mod.command_requests_debug("/dcoir-review debug yes", "/dcoir-review")
assert not mod.command_requests_debug("/dcoir-review debug=false", "/dcoir-review")
assert not mod.command_requests_debug("/dcoir-review --debug=false", "/dcoir-review")
assert not mod.command_requests_debug("/dcoir-review debug: false", "/dcoir-review")
debug_config = replace(config)
mod.apply_debug_flag(debug_config, "/dcoir-review debug", "/dcoir-review")
assert debug_config.debug is True
assert debug_config.post_progress_comment is True
assert not mod.command_matches("looks good", config.commands)
assert not mod.command_matches("/or-reviewer", config.commands)
assert not mod.command_matches("/dcoir-review-anything", config.commands)
assert mod.model_stack_label(config) == "openrouter/free"

fallback_fix_comment = mod.build_inline_comment(
    {
        "title": "Unsafe file write",
        "severity": "high",
        "confidence": 0.92,
        "path": "collector/run.ps1",
        "line": 10,
        "body": "The write path is request controlled.",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "powershell",
            "remove": "Set-Content -Path $Request.OutputPath -Value $Data",
            "replace": "$safePath = Join-Path -Path $AllowedRoot -ChildPath $Request.OutputName",
            "add": "if (-not $safePath.StartsWith($AllowedRoot)) { throw 'Path escaped allowed root.' }",
        },
        "validation": "",
    },
    "test-model",
    config,
)
assert "**On line 10 remove:**" in fallback_fix_comment
assert "**Replace with:**" in fallback_fix_comment
assert "```powershell" in fallback_fix_comment
assert "```suggestion" not in fallback_fix_comment
assert "```text" not in fallback_fix_comment
assert "pull\\_request\\_target" not in mod.build_inline_comment(
    {
        "title": "Unsafe pull_request_target workflow",
        "severity": "high",
        "confidence": 0.95,
        "path": ".github/workflows/probe.yml",
        "line": 4,
        "body": "Uses `pull_request_target` with untrusted code.",
        "validation": "python3 project_sources/github_actions/tools/build_workflow_inventory.py --check",
    },
    "test-model",
    config,
)

previous_openrouter_key = os.environ.pop("OPENROUTER_API_KEY", None)
try:
    try:
        mod.env_required("OPENROUTER_API_KEY")
    except RuntimeError as exc:
        assert "OPENROUTER_API_KEY" in str(exc)
    else:
        raise AssertionError("missing OPENROUTER_API_KEY should raise RuntimeError")
finally:
    if previous_openrouter_key is not None:
        os.environ["OPENROUTER_API_KEY"] = previous_openrouter_key

schema = json.loads((ROOT / "schemas" / "openrouter-pr-review.schema.json").read_text(encoding="utf-8"))
assert schema["properties"]["findings"]["type"] == "array"

secret_like = "sk_" + "live_demo_secret_value_123456"
redacted = mod.sanitize_text(f'token = "{secret_like}"', config)
assert "sk_live_demo" not in redacted
assert "[redacted-secret]" in redacted

openrouter_key = "sk-or-v1-" + "a" * 32
openai_key = "sk-proj-" + "b" * 32
password_value = "supersecretvalue12345"
punctuation_password = "p@ssw0rd123!"
dotted_password = "correct.horse.battery.staple"
delimiter_password = "abc12345;moresecret"
yaml_password = "yaml:style:password!"
quoted_json_password = "quoted-json-password!"
single_quoted_api_key = "single-quoted-api-key!"
apostrophe_password = "p@ss'word123!"
double_quote_password = 'p@ss"word123!'
escaped_quote_password = r'aaaaaaaa\"tail-secret'
bearer_secret = "bearer-secret-123456789"
basic_secret = "QmFzaWMtc2VjcmV0LTEyMzQ1Njc4OQ=="
cookie_secret = "sessionid=cookie-secret-123456789; connect.sid=connect-secret-123456789; csrf=csrf-secret-123456789"
set_cookie_secret = "refresh=refresh-cookie-secret-123456789; Path=/; HttpOnly"
url_password = "url-password-123456789!"
curl_password = "curl-password-123456789!"
curl_proxy_password = "proxy-curl-password-123456789!"
curl_spaced_password = "curl password secret 12345!"
curl_fallback_expression = "${{ secrets.CURL_PASSWORD || 'fallback curl secret 12345' }}"
curl_proxy_fallback_expression = "${{ secrets.PROXY_PASSWORD || 'proxy fallback secret 12345' }}"
curl_inner_brace_expression = "${{ secrets.CURL_PASSWORD || 'fallback }} curl secret 12345' }}"
curl_unclosed_expression = "${{ secrets.CURL_PASSWORD || 'unclosed curl secret 12345"
curl_backtick_expression = "`printf backtick curl secret 12345`"
curl_multiline_backtick_expression = "`printf multiline backtick curl secret 12345\n`"
curl_multiline_backtick_tail_expression = "`printf benign\nmultiline backtick tail secret 12345`"
curl_unclosed_quoted_password = "top quoted secret 12345"
curl_proxy_unclosed_quoted_password = "proxy top quoted secret 12345"
curl_multiline_double_quote_password = "multiline double quoted tail secret 12345"
curl_multiline_single_quote_password = "multiline single quoted tail secret 12345"
curl_multiline_ansi_quote_password = "multiline ansi quoted tail secret 12345"
curl_multiline_locale_quote_password = "multiline locale quoted tail secret 12345"
curl_ansi_password = "ansi curl secret 12345"
curl_locale_password = "locale curl secret 12345"
curl_escaped_space_password = r"escaped\ curl\ secret\ 12345"
curl_concat_password = "concat curl secret 12345"
netrc_password = "netrc-password-123456789!"
signed_url_secret = "signed-url-secret-123456789abcdef"
sas_secret = "azure-sas-secret-123456789abcdef"
private_key_block = "\n".join(
    [
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAlwAAAAdzc2gtcn",
        "NhAAAAAwEAAQAAAIEAprivate-key-secret-material-123456789",
        "-----END OPENSSH PRIVATE KEY-----",
    ]
)
quoted_env_reference = "${OPENROUTER_API_KEY}"
dollar_env_reference = "$DB_PASSWORD"
process_env_reference = "process.env.TOKEN"
github_secret_reference = "${{ secrets.OPENROUTER_TOKEN }}"
exact_os_getenv_reference = 'os.getenv("OPENROUTER_TOKEN")'
exact_secrets_reference = 'secrets.get("OPENROUTER_TOKEN")'
unsafe_process_reference = "process.env.TOKEN p@ss'word123!"
unsafe_getenv_reference = 'os.getenv("OPENROUTER_TOKEN") p@ssw0rd123!'
unsafe_secrets_reference = 'secrets.get("OPENROUTER_TOKEN") secret-tail-123!'
unsafe_process_suffix = "process.env.DB_PASSWORD;actual-secret-123"
unsafe_getenv_suffix = 'os.getenv("OPENROUTER_TOKEN")tail-secret'
unsafe_getenv_default = 'os.getenv("OPENROUTER_TOKEN", "fallback-secret-123")'
unsafe_process_concat = 'process.env.DB_PASSWORD + "actual-secret-456"'
unsafe_method_concat = 'os.getenv("OPENROUTER_TOKEN").strip() + "actual-secret-789"'
unsafe_shell_suffix = "${DB_PASSWORD}:actual-secret-000"
unsafe_f_string = "f\"{os.getenv('OPENROUTER_TOKEN')}:actual-secret-abc\""
github_secret_fallback = "${{ secrets.OPENROUTER_TOKEN || 'fallback-secret-456' }}"
aws_signed_url = f"https://bucket.s3.amazonaws.com/object?X-Amz-Credential={openrouter_key}&X-Amz-Signature={signed_url_secret}&X-Amz-Expires=3600"
azure_sas_url = f"https://account.blob.core.windows.net/container/blob?sv=2026-01-01&sp=r&sig={sas_secret}"
generic_signed_url = f"https://example.test/webhook?sig={signed_url_secret}&token={openrouter_key}"
