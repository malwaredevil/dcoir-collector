"""Canonical classification of fix-guidance values as code or prose."""

import ast
import re
import textwrap
from typing import Any

GUIDANCE_NATURAL_LANGUAGE_START_RE = re.compile(
    r"^\s*(?:"
    r"the\s+entire|if\s+a\s+|if\s+an\s+|when\s+|because\s+|use\s+|using\s+|"
    r"replace\s+|remove\s+|delete\s+|add\s+|ensure\s+|validate\s+|"
    r"no\s+replacement|a\s+complete|repair\s+steps|fixing\s+"
    r")\b",
    re.IGNORECASE,
)
GUIDANCE_NATURAL_LANGUAGE_WORD_RE = re.compile(
    r"\b(?:the|this|that|with|without|because|function|entire|required|"
    r"governed|evaluator|parser|allowlist|validates|before|after|safe|unsafe|"
    r"must|should|would|could|repair|fix|line|lines)\b",
    re.IGNORECASE,
)
GUIDANCE_FENCE_LINE_RE = re.compile(r"^\s*(?:```|~~~)")
GUIDANCE_YAML_CODE_RE = re.compile(r"(?m)^\s*(?:[-?]\s+)?[A-Za-z0-9_.${}/ -]+\s*:")
GUIDANCE_POWERSHELL_CODE_RE = re.compile(
    r"^\s*(?:#|param\s*\(|function\s+[A-Za-z_][A-Za-z0-9_-]*\b|"
    r"\$[A-Za-z_][A-Za-z0-9_]*\b|[A-Za-z]+-[A-Za-z]+(?:\s|$)|"
    r"(?:if|foreach|for|while|try|catch|finally)\s*(?:\(|\{))",
    re.IGNORECASE,
)
GUIDANCE_JS_TS_CODE_RE = re.compile(
    r"^\s*(?:const|let|var|return|if|for|while|throw|await|import|export|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*(?:=|=>|\())\b",
)


def _strip_guidance_fences(value: Any) -> str:
    lines: list[str] = []
    for line in str(value or "").splitlines():
        if GUIDANCE_FENCE_LINE_RE.match(line):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _guidance_is_natural_language(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    first = next((line.strip() for line in stripped.splitlines() if line.strip()), "")
    if GUIDANCE_NATURAL_LANGUAGE_START_RE.match(first):
        return True
    return len(first.split()) >= 5 and bool(GUIDANCE_NATURAL_LANGUAGE_WORD_RE.search(first))


def _python_guidance_is_code(value: str) -> bool:
    try:
        ast.parse(textwrap.dedent(value).strip() + "\n")
        return True
    except SyntaxError:
        return False


def _powershell_guidance_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and all(
        GUIDANCE_POWERSHELL_CODE_RE.match(line) or line.strip() in {"}", "};"}
        for line in lines
    )


def _yaml_guidance_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and any(GUIDANCE_YAML_CODE_RE.match(line) for line in lines) and not _guidance_is_natural_language(value)


def _javascript_guidance_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and any(GUIDANCE_JS_TS_CODE_RE.match(line) for line in lines) and not _guidance_is_natural_language(value)


def guidance_value_looks_like_code(value: Any, language: str) -> bool:
    """Return whether a guidance value is syntactically code-like for its language."""
    text = _strip_guidance_fences(value)
    if not text or _guidance_is_natural_language(text):
        return False
    normalized_language = str(language or "").lower()
    if normalized_language == "python":
        return _python_guidance_is_code(text)
    if normalized_language == "powershell":
        return _powershell_guidance_is_code(text)
    if normalized_language in {"yaml", "json"}:
        return _yaml_guidance_is_code(text)
    if normalized_language in {"typescript", "javascript"}:
        return _javascript_guidance_is_code(text)
    return any(signal in text for signal in ("=", "$", ":", "(", "{", "|", ";"))
