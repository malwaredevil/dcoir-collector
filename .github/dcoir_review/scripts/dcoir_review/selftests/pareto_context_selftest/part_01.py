#!/usr/bin/env python3
"""Offline checks for Pareto routing and first-pass context wrapper."""

from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock


ROOT = next(
    (
        candidate
        for candidate in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]
        if candidate.name == "dcoir_review"
        and (candidate / "scripts" / "openrouter_pr_review_pareto_context.py").is_file()
        and (candidate / "schemas").is_dir()
    ),
    None,
)
if ROOT is None:
    raise SystemExit("unable to locate .github/dcoir_review root")
SCRIPT = ROOT / "scripts" / "openrouter_pr_review_pareto_context.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review_pareto_context", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review_pareto_context.py")
mod = importlib.util.module_from_spec(spec)

sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

os.environ["GITHUB_REPOSITORY"] = "DCOIR-Collector/dcoir-collector"
os.environ["PR_NUMBER"] = "287"
os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

config = mod.load_pareto_context_config(str(ROOT / "openrouter-pr-review-pareto.yml"))
assert config.model == "anthropic/claude-opus-5"
assert config.model_stack == ["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"]
assert config.pareto_min_coding_score == 0.80
assert config.auto_cost_quality_tradeoff == 2
assert "google/gemini-*" not in config.auto_allowed_models
assert "google/gemini-3.1-pro-preview*" in config.auto_allowed_models
assert "google/gemini-3.1-pro*" not in config.auto_allowed_models
assert config.first_pass_deep_review is True
assert config.max_files == 100
assert config.deep_review_max_files == 20
# Issue #456 acceptance cycle intentionally enables debug so blind-review
# candidate/verifier artifacts can be inspected. Revert this to False with the
# governed config after recall acceptance is proven.
assert config.debug is True
assert config.post_progress_comment is False
assert config.per_file_first_pass_review is True
assert config.per_file_review_concurrency == 6
assert config.per_file_review_max_files == 100
assert config.fix_synthesis_enabled is True
assert config.required_finding_reserved_budget == 9
assert config.required_finding_min_per_family == 2


fix_synthesis_verifier_marker = "single-line-pr-head-anchor"
fix_file_text = "def restore(raw_state):\n    state = decode_state(raw_state)\n    return state\n"
fix_replacement = "    state = json.loads(raw_state)"
assert mod.verified_suggested_replacement(
    {"suggested_replacement": fix_replacement},
    fix_file_text,
    2,
    config,
) == fix_replacement
assert mod.verified_suggested_replacement(
    {"suggested_replacement": "    state = decode_state(raw_state)"},
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
    {"suggested_replacement": "    state = decode_state(raw_state) ~~~"},
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
            "remove": "decode_state(raw_state)",
            "replace": "json.loads(raw_state)",
            "add": "Add a JSON schema validation test for the accepted state shape.",
            "notes": "Keep the repair limited to the deserialization path.",
        },
    },
    "test-model",
    config,
)
assert "**On line 0 remove:**" not in fallback_fix_comment
assert "**On line" not in fallback_fix_comment
assert "**Remove:**" in fallback_fix_comment
assert "**Replace with:**" in fallback_fix_comment
assert "**Add:**" in fallback_fix_comment
assert "Keep the repair limited" in fallback_fix_comment
assert "```suggestion" not in fallback_fix_comment
assert "**Notes:**" in fallback_fix_comment
assert "```text\nKeep the repair limited to the deserialization path.\n```" not in fallback_fix_comment

malformed_guidance_comment = mod.base.build_inline_comment(
    {
        "path": "project_sources/collector/tools/dcoir_review_intentional_python_probe.py",
        "title": "Malformed fix guidance",
        "severity": "high",
        "confidence": 0.95,
        "body": "The repair formatter should not render nested fences or malformed validation commands.",
        "validation": "python3 -m py_compile project_sources/collector/tools/dcoir_review_intentional_python_probe.py && python3 -c \"\npython3 -m py_compile project_sources/collector/tools/dcoir_review_intentional_python_probe.py\nbandit -r project_sources/collector/tools/dcoir_review_intentional_python_probe.py",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "powershell",
            "add": "```powershell\nWrite-Output \"safe\"\n```",
        },
    },
    "test-model",
    config,
)
assert "```powershell\n```powershell" not in malformed_guidance_comment
assert "Write-Output \"safe\"" in malformed_guidance_comment
assert 'python3 -m py_compile project_sources/collector/tools/dcoir_review_intentional_python_probe.py && python3 -c "' not in malformed_guidance_comment
assert "bandit -r project_sources/collector/tools/dcoir_review_intentional_python_probe.py" in malformed_guidance_comment

heading_notes_comment = mod.base.build_inline_comment(
    {
        "title": "Global state write",
        "severity": "high",
        "confidence": 0.95,
        "body": "Fallback notes must not escape into markdown headings.",
        "validation": "pwsh -NoProfile -Command Invoke-ScriptAnalyzer -Path probe.ps1",
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
assert "**Notes:**" in heading_notes_comment
assert "```text\n# The function should record state through governed storage, not global scope.\n```" not in heading_notes_comment
assert "# The function should record state through governed storage, not global scope." in heading_notes_comment

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
