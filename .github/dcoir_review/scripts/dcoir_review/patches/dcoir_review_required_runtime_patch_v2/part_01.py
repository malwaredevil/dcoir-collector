"""Second required-coverage layer for DCOIR Review.

This module runs after the runtime, strict, and required patch layers. It keeps
connector-sized changes small while fixing live-test regressions around required
PowerShell ACL coverage, token wording, YAML validation formatting, and final
comment renderer ordering.
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patches as required

PS_ACL_KIND = "ps_acl"
HARD_REQUIRED_KIND_TITLES = {
    **required.YAML_REQUIRED_KIND_TITLES,
    PS_ACL_KIND: "PowerShell broad ACL grant exposes collector output",
}
HARD_REQUIRED_KIND_ORDER = (
    "yaml_pull_request_target",
    "yaml_broad_write",
    "yaml_untrusted_checkout",
    "yaml_shell_pipe",
    PS_ACL_KIND,
)
REQUIRED_KIND_ORDER = (
    *HARD_REQUIRED_KIND_ORDER,
    "python_shell_exec",
    "python_dynamic_exec",
    "python_pickle",
    "python_yaml_load",
    "python_archive_extract",
    "python_ssrf",
    "ps_dynamic_exec",
    "ps_archive_extract",
    "ps_process_launch",
    "ps_outbound_token",
)
PS_ACL_SENTINEL_LABEL = "DCOIR PowerShell broad ACL grant"
PS_ACL_SENTINEL_DETAIL = "broad ACL grants such as Everyone or FullControl expose collector output and execution surfaces"
ENV_TOKEN_RE = re.compile(r"(?:os\.environ|os\.getenv|\$env:|process\.env|Environment::GetEnvironmentVariable|DCOIR_TOKEN)", re.IGNORECASE)
TOKEN_FORWARDING_RE = re.compile(r"(?:Authorization|Bearer|callback|Invoke-RestMethod|Invoke-WebRequest|requests\.(?:get|post|put|request)|urlopen)", re.IGNORECASE)
BRACKETED_REDACTION_RE = re.compile(r"\[redacted[-_ ]?(?:secret|token|credential|api key)?\]", re.IGNORECASE)
HARDCODED_TOKEN_RE = re.compile(
    r"\b(?:hard[- ]?coded|literal|redacted)\s+(?:bearer\s+)?(?:secret-like\s+)?(?:secret|token|credential|api key|value)\b",
    re.IGNORECASE,
)
HARDCODED_BEARER_RE = re.compile(r"\bhard[- ]?coded\s+bearer\s+token\b", re.IGNORECASE)
LITERAL_BEARER_VALUE_RE = re.compile(r"\bliteral\s+bearer\s+token\s+value\b", re.IGNORECASE)
NATURAL_LANGUAGE_START_RE = re.compile(
    r"^\s*(?:the\s+entire|if\s+|when\s+|because\s+|replace\s+|remove\s+|delete\s+|add\s+|ensure\s+|use\s+|using\s+|no\s+replacement|a\s+complete|repair\s+steps|fix\s+)",
    re.IGNORECASE,
)
NATURAL_LANGUAGE_WORD_RE = re.compile(
    r"\b(?:the|this|that|with|without|because|function|entire|required|governed|parser|allowlist|validates|before|after|safe|unsafe|must|should|would|could|repair|line|lines)\b",
    re.IGNORECASE,
)
POWERSHELL_CODE_RE = re.compile(
    r"^\s*(?:#|param\s*\(|function\s+[A-Za-z_][A-Za-z0-9_-]*\b|\$[A-Za-z_][A-Za-z0-9_]*\b|[A-Za-z]+-[A-Za-z]+(?:\s|$)|(?:if|foreach|for|while|try|catch|finally)\s*(?:\(|\{))",
    re.IGNORECASE,
)
YAML_CODE_RE = re.compile(r"(?m)^\s*(?:[-?]\s+)?[A-Za-z0-9_.${}/ -]+\s*:")
JS_TS_CODE_RE = re.compile(r"^\s*(?:const|let|var|return|if|for|while|throw|await|import|export|[A-Za-z_][A-Za-z0-9_]*\s*(?:=|=>|\())\b")


def _normalize(value: Any) -> str:
    return required._normalize(value)


def _line_kind(path: str, text: str) -> str:
    return required._line_semantic_kind(path, text)


def _semantic_kind(finding: dict[str, Any]) -> str:
    return required._semantic_kind(finding)


def _sentinel_kind(sentinel: Any) -> str:
    return required._sentinel_kind(sentinel)


def _sentinel_line(sentinel: Any) -> int:
    try:
        return int(getattr(sentinel, "line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _finding_line(finding: dict[str, Any]) -> int:
    try:
        return int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe_sentinel_key(sentinel: Any) -> tuple[str, int, str]:
    path = str(getattr(sentinel, "path", "") or "")
    kind = _sentinel_kind(sentinel) or str(getattr(sentinel, "label", "") or "")
    line = 0 if kind == PS_ACL_KIND else _sentinel_line(sentinel)
    return path, line, kind


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    for sentinel in sentinels:
        key = _dedupe_sentinel_key(sentinel)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentinel)
    return deduped


def _make_ps_acl_sentinels(hardened: Any, diff: str) -> list[Any]:
    iter_added = getattr(hardened, "iter_added_diff_lines", None)
    risk_sentinel_type = getattr(hardened, "RiskSentinel", None)
    if not callable(iter_added) or risk_sentinel_type is None:
        return []
    sentinels: list[Any] = []
    for changed_line in iter_added(diff):
        path = str(getattr(changed_line, "path", "") or "")
        text = str(getattr(changed_line, "text", "") or "")
        if Path(path.lower()).suffix not in {".ps1", ".psm1", ".psd1"}:
            continue
        if callable(getattr(hardened, "is_comment_only_added_line", None)) and hardened.is_comment_only_added_line(path, text):
            continue
        if _line_kind(path, text) != PS_ACL_KIND:
            continue
        line = _sentinel_line(changed_line)
        if line <= 0:
            continue
        sentinels.append(
            risk_sentinel_type(
                path=path,
                line=line,
                label=PS_ACL_SENTINEL_LABEL,
                detail=PS_ACL_SENTINEL_DETAIL,
                text=text,
            )
        )
    return _dedupe_sentinels(sentinels)


def _select_sentinels(hardened: Any, sentinels: list[Any], max_anchors: int | None) -> list[Any]:
    deduped = _dedupe_sentinels(sentinels)
    if max_anchors is None or len(deduped) <= max_anchors:
        return deduped
    if max_anchors <= 0:
        return []
    selected: list[Any] = []
    seen: set[tuple[str, int, str]] = set()

    def add(sentinel: Any) -> None:
        key = _dedupe_sentinel_key(sentinel)
        if key not in seen and len(selected) < max_anchors:
            seen.add(key)
            selected.append(sentinel)

    for kind in HARD_REQUIRED_KIND_ORDER:
        for sentinel in deduped:
            if _sentinel_kind(sentinel) == kind:
                add(sentinel)
                break
    remaining = [sentinel for sentinel in deduped if _dedupe_sentinel_key(sentinel) not in seen]
    original_select = getattr(hardened, "_dcoir_required_v2_original_select_risk_sentinels", None)
    if not callable(original_select):
        original_select = getattr(hardened, "_dcoir_required_original_select_risk_sentinels", None)
    if not callable(original_select):
        original_select = getattr(hardened, "select_risk_sentinels", None)
    if callable(original_select):
        try:
            remaining = original_select(remaining, max_anchors - len(selected))
        except TypeError:
            remaining = original_select(remaining)
    for sentinel in remaining:
        add(sentinel)
    return selected


def _validation_for_path(path: str, kind: str = "") -> str:
    lower_path = path.lower()
    if lower_path.endswith((".yml", ".yaml")):
        checks = ["assert path.exists(), path"]
        if kind == "yaml_pull_request_target":
            checks.append("assert 'pull_request_target' not in text")
        elif kind == "yaml_broad_write":
            checks.append("assert 'write-all' not in text and ': write' not in text")
        elif kind == "yaml_untrusted_checkout":
            checks.append("assert 'github.event.pull_request.head' not in text and 'github.head_ref' not in text")
        elif kind == "yaml_shell_pipe":
            checks.append("assert '| bash' not in text and '| sh' not in text")
        else:
            checks.append("assert text.strip()")
        script = f"from pathlib import Path; path=Path({path!r}); text=path.read_text(encoding='utf-8'); " + "; ".join(checks)
        return f"python3 -c {shlex.quote(script)}"
    return required._validation_for_path(path, kind)
