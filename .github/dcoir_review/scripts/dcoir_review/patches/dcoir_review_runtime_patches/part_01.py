"""Connector-safe runtime patches for DCOIR Review entrypoints.

The large reviewer scripts are intentionally left connector-safe by patching narrow
runtime hooks from this module. ``openrouter_pr_review_entrypoint.py`` imports the
Pareto reviewer, calls ``apply_pareto_context_module()``, then invokes the real
main function.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REVIEW_ENTRYPOINTS = {"openrouter_pr_review.py", "openrouter_pr_review_pareto_context.py"}

PROSE_GUIDANCE_START_RE = re.compile(
    r"^(?:"
    r"add|avoid|change|delete|do not|ensure|example|keep|line|lines|move|native|"
    r"on\s+line|on\s+lines|replace|remove|run|store|use|validate"
    r")\b",
    re.IGNORECASE,
)
PROSE_WORD_RE = re.compile(
    r"\b(?:the|this|that|with|without|because|comment|current|entire|line|lines|"
    r"near|safe|unsafe|stating|version|must|should|would|could)\b",
    re.IGNORECASE,
)
YAML_KEY_RE = re.compile(r"(?m)^\s*[A-Za-z0-9_.-]+\s*:")
PYTHON_CODE_LINE_RE = re.compile(
    r"^\s*(?:"
    r"@|from\s+\S+\s+import\s+|import\s+|def\s+|async\s+def\s+|class\s+|"
    r"if\s+|elif\s+|else:|for\s+|while\s+|try:|except\b|finally:|with\s+|"
    r"return\b|raise\b|assert\b|[A-Za-z_][A-Za-z0-9_]*\s*(?::\s*[^=]+)?="
    r")"
)
POWERSHELL_CODE_LINE_RE = re.compile(
    r"^\s*(?:#|\$[A-Za-z_][A-Za-z0-9_]*|"
    r"[A-Za-z]+-[A-Za-z]+(?:\s|$)|"
    r"(?:if|foreach|for|while|try|catch|finally|param|function)\b)",
    re.IGNORECASE,
)
CURL_BASH_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\|\s*(?:bash|sh)\b|bash\b|sh\b)", re.IGNORECASE)
GH_WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|"
    r"(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
PYTHON_DYNAMIC_EXEC_CALL_RE = re.compile(r"\b(?:eval|exec)\s*\(")
INLINE_DUNDER_RE = re.compile(r"(?<![`\\])\b(__[A-Za-z][A-Za-z0-9_]*__)\b(?!`)")
FENCE_LINE_RE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


_KIND_TITLES = {
    "python_pickle": "Unsafe Python pickle deserialization",
    "python_yaml_load": "Unsafe YAML loader for untrusted input",
    "python_ssrf": "Outbound request can be steered by untrusted input",
    "python_dynamic_exec": "Dynamic Python execution of untrusted input",
    "ps_securestring": "Plaintext SecureString conversion",
    "ps_start_process": "Unvalidated process launch",
    "ps_run_key": "Windows Run key persistence change",
    "yaml_pull_request_target": "Privileged pull_request_target workflow context",
    "yaml_broad_write": "GitHub Actions workflow grants write permissions",
    "yaml_untrusted_checkout": "Privileged workflow checks out untrusted PR code",
    "yaml_shell_pipe": "Workflow pipes a network installer into a shell",
}

_KIND_DEFAULT_NOTES = {
    "python_pickle": "Use a non-executing serialization format such as JSON or a typed schema for untrusted data; do not deserialize untrusted pickle payloads.",
    "python_yaml_load": "Use yaml.safe_load or SafeLoader for untrusted YAML input.",
    "python_ssrf": "Validate outbound URLs against an allowlist and block private, loopback, link-local, and metadata-service ranges before making the request.",
    "ps_start_process": "Validate the executable path and arguments against an allowlist before launching a process.",
    "yaml_shell_pipe": "Download to a file, verify a pinned checksum or signature, then execute only verified content.",
}

_INTERNAL_LINE_RE = re.compile(
    r"(?:deterministic risk sentinel|dcoir-review-guard\.yml|guard workflow|non-evidenced guard)",
    re.IGNORECASE,
)
MISMATCHED_DYNAMIC_RE = re.compile(
    r"\b(?:dynamic python execution|dynamic evaluation|eval\s+or\s+exec|eval/exec|ast\.literal_eval|restricted globals)\b",
    re.IGNORECASE,
)


def _first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _strip_markdown_fence_lines(text: str) -> str:
    lines: list[str] = []
    for line in str(text or "").splitlines():
        if FENCE_LINE_RE.match(line):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _line_looks_like_code(line: str, language: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()
    if not stripped:
        return False
    if language in {"yaml", "json"} and YAML_KEY_RE.match(stripped):
        return True
    if language == "python" and PYTHON_CODE_LINE_RE.match(stripped):
        return True
    if language == "powershell" and POWERSHELL_CODE_LINE_RE.match(stripped):
        return True
    code_signals = (
        "$",
        "=",
        "(",
        ")",
        "{",
        "}",
        "[",
        "]",
        ";",
        "|",
        "=>",
        "&&",
        "||",
        "import ",
        "from ",
        "def ",
        "class ",
        "return ",
        "raise ",
        "throw ",
        "if ",
        "for ",
        "while ",
        "on:",
        "permissions:",
        "uses:",
        "run:",
        "set-",
        "invoke-",
        "start-",
        "convertto-",
    )
    return any(signal_text in lowered for signal_text in code_signals)


def _guidance_value_is_prose(value: str, language: str) -> bool:
    first = _first_nonempty_line(value)
    if not first:
        return False
    if PROSE_GUIDANCE_START_RE.match(first):
        return True
    if _line_looks_like_code(first, language):
        return False
    return len(first.split()) >= 5 and bool(PROSE_WORD_RE.search(first))


def patched_guidance_value_looks_like_code(value: str, language: str) -> bool:
    stripped = _strip_markdown_fence_lines(value)
    if not stripped:
        return False
    normalized_language = str(language or "").strip().lower()
    if _guidance_value_is_prose(stripped, normalized_language):
        return False
    if normalized_language in {"yaml", "json"} and YAML_KEY_RE.search(stripped):
        return True
    lines = [line for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False
    code_line_count = sum(1 for line in lines if _line_looks_like_code(line, normalized_language))
    if not code_line_count:
        return False
    prose_line_count = sum(1 for line in lines if _guidance_value_is_prose(line, normalized_language))
    return code_line_count >= max(1, len(lines) - prose_line_count)


def _protect_markdown_identifiers(value: str) -> str:
    return INLINE_DUNDER_RE.sub(r"`\1`", str(value or ""))


def _remove_internal_lines(value: str) -> str:
    kept: list[str] = []
    for line in str(value or "").splitlines():
        if _INTERNAL_LINE_RE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _clean_user_text(value: str) -> str:
    return _protect_markdown_identifiers(_remove_internal_lines(value))


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _finding_text(finding: dict[str, Any], key: str = "") -> str:
    values = [
        str(finding.get("title", "") or ""),
        str(finding.get("body", "") or ""),
        str(finding.get("validation", "") or ""),
    ]
    fix_guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if fix_guidance:
        values.extend(str(fix_guidance.get(name, "") or "") for name in ("remove", "replace", "add", "notes"))
    if key:
        values = [str(finding.get(key, "") or "")]
    return _normalize("\n".join(values))
