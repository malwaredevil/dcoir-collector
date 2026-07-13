"""Third required-coverage layer for DCOIR Review.

This layer keeps the previous connector-sized patches intact and fixes the next
set of live-test regressions: required Start-Process coverage, final token-wording
scrubbing, prose validation rejection, PR-metadata shell anchoring, whole-file
fallback guidance, and Python replacement indentation.
"""

from __future__ import annotations

import ast
import re
import shlex
import textwrap
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v2 as v2

_strip_fences = v2._strip_fences
import dcoir_review_required_runtime_patches as required

PS_PROCESS_KIND = "ps_process_launch"
YAML_METADATA_SHELL_KIND = "yaml_metadata_shell"
HARD_REQUIRED_KIND_TITLES = {
    **v2.HARD_REQUIRED_KIND_TITLES,
    PS_PROCESS_KIND: "PowerShell caller-controlled process launch",
}
OPTIONAL_KIND_TITLES = {
    YAML_METADATA_SHELL_KIND: "Workflow executes pull request metadata in a shell",
}
HARD_REQUIRED_KIND_ORDER = (
    "yaml_pull_request_target",
    "yaml_broad_write",
    "yaml_untrusted_checkout",
    "yaml_shell_pipe",
    v2.PS_ACL_KIND,
    PS_PROCESS_KIND,
)
RANK_KIND_ORDER = (
    *HARD_REQUIRED_KIND_ORDER,
    "python_shell_exec",
    "python_dynamic_exec",
    "python_pickle",
    "python_yaml_load",
    "python_archive_extract",
    "python_ssrf",
    "ps_dynamic_exec",
    "ps_archive_extract",
    "ps_outbound_token",
    YAML_METADATA_SHELL_KIND,
)
PS_PROCESS_LABEL = "DCOIR PowerShell process launch"
PS_PROCESS_DETAIL = "caller-controlled Start-Process execution must be allowlisted or removed"
YAML_METADATA_LABEL = "DCOIR YAML pull request metadata shell execution"
YAML_METADATA_DETAIL = "pull request metadata is piped or passed into a shell command"
PR_METADATA_SHELL_RE = re.compile(
    r"github\.event\.pull_request\.(?:body|title|head\.ref|head\.sha)[^\n]*(?:\|\s*(?:bash|sh)\b|\bbash\b|\bsh\b)",
    re.IGNORECASE,
)
PS_START_PROCESS_RE = re.compile(r"\bStart-Process\b", re.IGNORECASE)
ENV_TOKEN_RE = re.compile(r"(?:os\.environ|os\.getenv|\$env:|process\.env|Environment::GetEnvironmentVariable|DCOIR_TOKEN)", re.IGNORECASE)
TOKEN_CONTEXT_RE = re.compile(r"(?:Authorization|Bearer|callback|Invoke-RestMethod|Invoke-WebRequest|requests\.(?:get|post|put|request)|urlopen)", re.IGNORECASE)
REDACTED_RE = re.compile(r"\[redacted[-_ ]?(?:secret|token|credential|api key)?\]", re.IGNORECASE)
PROSE_VALIDATION_RE = re.compile(r"\b(?:scan for|without validatation|without validation|after correction|manually verify|guidance|expected after fix)\b", re.IGNORECASE)
COMMAND_START_RE = re.compile(r"^\s*(?:python3?|pytest|bandit|pwsh|powershell|grep|rg|yamllint|npm|npx|node|bash|sh)\b")


def _normalize(value: Any) -> str:
    return required._normalize(value)


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    if suffix in {".ps1", ".psm1", ".psd1"} and PS_START_PROCESS_RE.search(str(text or "")):
        return PS_PROCESS_KIND
    if suffix in {".yml", ".yaml"} and PR_METADATA_SHELL_RE.search(str(text or "")):
        return YAML_METADATA_SHELL_KIND
    return v2._line_kind(path, text)


def _semantic_kind(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "")
    anchored = str(finding.get("_anchored_line_text", "") or "")
    anchored_kind = _line_kind(path, anchored)
    if anchored_kind:
        return anchored_kind
    text = _normalize("\n".join(str(finding.get(key, "") or "") for key in ("title", "body", "validation")))
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    text += "\n" + _normalize("\n".join(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes")))
    if Path(path.lower()).suffix in {".yml", ".yaml"}:
        if PR_METADATA_SHELL_RE.search(text) or ("pull_request.body" in text and "bash" in text) or ("pull request body" in text and "bash" in text):
            return YAML_METADATA_SHELL_KIND
    return v2._semantic_kind(finding)


def _sentinel_kind(sentinel: Any) -> str:
    path = str(getattr(sentinel, "path", "") or "")
    text = str(getattr(sentinel, "text", "") or "")
    line_kind = _line_kind(path, text)
    if line_kind:
        return line_kind
    combined = _normalize("\n".join(str(getattr(sentinel, key, "") or "") for key in ("label", "detail")))
    if "process launch" in combined or "start-process" in combined:
        return PS_PROCESS_KIND
    if "metadata" in combined and "shell" in combined:
        return YAML_METADATA_SHELL_KIND
    return v2._sentinel_kind(sentinel)


def _finding_line(finding: dict[str, Any]) -> int:
    try:
        return int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _sentinel_line(sentinel: Any) -> int:
    try:
        return int(getattr(sentinel, "line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _sentinel_key(sentinel: Any) -> tuple[str, int, str]:
    kind = _sentinel_kind(sentinel) or str(getattr(sentinel, "label", "") or "")
    line = 0 if kind == v2.PS_ACL_KIND else _sentinel_line(sentinel)
    return str(getattr(sentinel, "path", "") or ""), line, kind


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    for sentinel in sentinels:
        key = _sentinel_key(sentinel)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentinel)
    return deduped


def _make_v3_sentinels(hardened: Any, diff: str) -> list[Any]:
    iter_added = getattr(hardened, "iter_added_diff_lines", None)
    risk_sentinel_type = getattr(hardened, "RiskSentinel", None)
    if not callable(iter_added) or risk_sentinel_type is None:
        return []
    sentinels: list[Any] = []
    for changed_line in iter_added(diff):
        path = str(getattr(changed_line, "path", "") or "")
        text = str(getattr(changed_line, "text", "") or "")
        if callable(getattr(hardened, "is_comment_only_added_line", None)) and hardened.is_comment_only_added_line(path, text):
            continue
        kind = _line_kind(path, text)
        if kind == PS_PROCESS_KIND:
            sentinels.append(risk_sentinel_type(path=path, line=_sentinel_line(changed_line), label=PS_PROCESS_LABEL, detail=PS_PROCESS_DETAIL, text=text))
        elif kind == YAML_METADATA_SHELL_KIND:
            sentinels.append(risk_sentinel_type(path=path, line=_sentinel_line(changed_line), label=YAML_METADATA_LABEL, detail=YAML_METADATA_DETAIL, text=text))
    return _dedupe_sentinels(sentinels)


def _select_sentinels(hardened: Any, sentinels: list[Any], max_anchors: int | None) -> list[Any]:
    deduped = _dedupe_sentinels(sentinels)
    if max_anchors is None or len(deduped) <= max_anchors:
        return deduped
    selected: list[Any] = []
    seen: set[tuple[str, int, str]] = set()

    def add(sentinel: Any) -> None:
        key = _sentinel_key(sentinel)
        if key not in seen and len(selected) < max_anchors:
            seen.add(key)
            selected.append(sentinel)

    for kind in HARD_REQUIRED_KIND_ORDER:
        for sentinel in deduped:
            if _sentinel_kind(sentinel) == kind:
                add(sentinel)
                break
    remaining = [sentinel for sentinel in deduped if _sentinel_key(sentinel) not in seen]
    original_select = getattr(hardened, "_dcoir_required_v3_original_select_risk_sentinels", None)
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


def _token_context(finding: dict[str, Any]) -> bool:
    haystack = "\n".join(str(finding.get(key, "") or "") for key in ("title", "body", "validation", "_anchored_line_text"))
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    haystack += "\n" + "\n".join(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))
    kind = _semantic_kind(finding)
    return kind in {"python_ssrf", "ps_outbound_token"} and (ENV_TOKEN_RE.search(haystack) is not None or TOKEN_CONTEXT_RE.search(haystack) is not None)
