"""Strict runtime patches for DCOIR Review fix synthesis and required YAML coverage."""

from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path
from typing import Any


NATURAL_LANGUAGE_START_RE = re.compile(
    r"^\s*(?:"
    r"the\s+entire|if\s+a\s+|if\s+an\s+|when\s+|because\s+|use\s+|using\s+|"
    r"replace\s+|remove\s+|delete\s+|add\s+|ensure\s+|validate\s+|"
    r"no\s+replacement|a\s+complete|repair\s+steps|fixing\s+"
    r")\b",
    re.IGNORECASE,
)
NATURAL_LANGUAGE_WORD_RE = re.compile(
    r"\b(?:the|this|that|with|without|because|function|entire|required|"
    r"governed|evaluator|parser|allowlist|validates|before|after|safe|unsafe|"
    r"must|should|would|could|repair|fix|line|lines)\b",
    re.IGNORECASE,
)
FENCE_LINE_RE = re.compile(r"^\s*(?:```|~~~)")
YAML_CODE_RE = re.compile(r"(?m)^\s*(?:[-?]\s+)?[A-Za-z0-9_.${}/ -]+\s*:")
POWERSHELL_CODE_RE = re.compile(
    r"^\s*(?:#|param\s*\(|function\s+[A-Za-z_][A-Za-z0-9_-]*\b|"
    r"\$[A-Za-z_][A-Za-z0-9_]*\b|[A-Za-z]+-[A-Za-z]+(?:\s|$)|"
    r"(?:if|foreach|for|while|try|catch|finally)\s*(?:\(|\{))",
    re.IGNORECASE,
)
JS_TS_CODE_RE = re.compile(
    r"^\s*(?:const|let|var|return|if|for|while|throw|await|import|export|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*(?:=|=>|\())\b",
)
PYTHON_DYNAMIC_EXEC_CALL_RE = re.compile(r"\b(?:eval|exec)\s*\(")
CURL_SHELL_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\|\s*(?:bash|sh)\b|bash\b|sh\b)", re.IGNORECASE)
GH_WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|"
    r"(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
INTERNAL_LINE_RE = re.compile(r"deterministic risk sentinel", re.IGNORECASE)
MARKDOWN_DUNDER_RE = re.compile(r"(?<![`\\])\b(__[A-Za-z][A-Za-z0-9_]*__)\b(?!`)")

STRICT_FIX_SYNTHESIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Review Strict Fix Synthesis",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "suggested_replacement",
        "remove_code",
        "replace_code",
        "add_code",
        "notes",
        "validation",
        "language",
        "start_line",
        "end_line",
    ],
    "properties": {
        "suggested_replacement": {
            "type": "string",
            "description": "Exact single-line replacement code for the anchored GitHub review line only, or empty.",
        },
        "remove_code": {
            "type": "string",
            "description": "Exact code/config text copied from the file that should be removed. Empty if not exact.",
        },
        "replace_code": {
            "type": "string",
            "description": "Exact replacement code/config only. Empty if conceptual or uncertain.",
        },
        "add_code": {
            "type": "string",
            "description": "Exact code/config to add only. Empty if conceptual or uncertain.",
        },
        "notes": {
            "type": "string",
            "description": "All prose guidance, caveats, and multi-line repair explanation.",
        },
        "validation": {
            "type": "string",
            "description": "Exact validation command or commands only.",
        },
        "language": {"type": "string"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
    },
}

YAML_REQUIRED_KIND_TITLES = {
    "yaml_pull_request_target": "Privileged `pull_request_target` workflow context",
    "yaml_broad_write": "GitHub Actions workflow grants write permissions",
    "yaml_untrusted_checkout": "Privileged workflow checks out untrusted PR code",
    "yaml_shell_pipe": "Workflow pipes a network installer into a shell",
}


def _strip_fences(value: Any) -> str:
    lines: list[str] = []
    for line in str(value or "").splitlines():
        if FENCE_LINE_RE.match(line):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _clean_public_text(value: str) -> str:
    lines = [line for line in str(value or "").splitlines() if not INTERNAL_LINE_RE.search(line)]
    return MARKDOWN_DUNDER_RE.sub(r"`\1`", "\n".join(lines).strip())


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _language_hint(path: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    return {
        ".bash": "bash",
        ".cjs": "javascript",
        ".js": "javascript",
        ".json": "json",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _finding_text(finding: dict[str, Any]) -> str:
    parts = [
        str(finding.get("title", "") or ""),
        str(finding.get("body", "") or ""),
        str(finding.get("validation", "") or ""),
    ]
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    parts.extend(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))
    return _normalize("\n".join(parts))


def _semantic_kind(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "").strip().lower()
    suffix = Path(path).suffix
    text = _finding_text(finding)
    if suffix == ".py":
        if "extractall" in text or "tarfile" in text or "archive extraction" in text:
            return "python_archive_extract"
        if "requests." in text or "ssrf" in text or "callback" in text:
            return "python_ssrf"
        if PYTHON_DYNAMIC_EXEC_CALL_RE.search(text) or "dynamic code execution" in text:
            return "python_dynamic_exec"
        if "pickle" in text:
            return "python_pickle"
        if "yaml.load" in text or "yaml.loader" in text:
            return "python_yaml_load"
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in text:
            return "ps_dynamic_exec"
        if "expand-archive" in text:
            return "ps_archive_extract"
        if "invoke-webrequest" in text or "invoke-restmethod" in text or "bearer" in text:
            return "ps_outbound_token"
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in text:
            return "yaml_pull_request_target"
        if "github.head_ref" in text or "github.event.pull_request.head" in text:
            return "yaml_untrusted_checkout"
        if (
            "untrusted checkout" in text
            or "checks out untrusted" in text
            or "checkout uses untrusted" in text
            or "untrusted pr code" in text
            or "pull request head ref" in text
            or "head ref or sha" in text
        ):
            return "yaml_untrusted_checkout"
        if ("curl" in text or "wget" in text) and ("|" in text or "pipe" in text) and ("bash" in text or " sh" in text):
            return "yaml_shell_pipe"
        if "write-all" in text or ("permissions" in text and "write" in text):
            return "yaml_broad_write"
    return ""


def _sentinel_kind(sentinel: Any) -> str:
    text = _normalize(
        "\n".join(
            [
                str(getattr(sentinel, "label", "") or ""),
                str(getattr(sentinel, "detail", "") or ""),
                str(getattr(sentinel, "text", "") or ""),
            ]
        )
    )
    path = str(getattr(sentinel, "path", "") or "")
    return _semantic_kind({"path": path, "title": text, "body": text})
