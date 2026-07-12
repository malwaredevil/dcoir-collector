"""Seventh required-coverage layer for DCOIR Review.

PR #330 showed that required findings can be present in model output but still
fail final enforcement after normalization, ranking, and refill. v7 uses a
stable required-sentinel ledger keyed by path, line, and semantic kind, and it
preserves safe interpolated bearer-token source syntax during redaction.
"""

from __future__ import annotations

import re
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v6 as v6

SentinelKey = tuple[str, int, str]

SAFE_AUTH_LINE_RE = re.compile(r"(?im)^.*(?:authorization|bearer).*$")
STATIC_BEARER_RE = re.compile(r"bearer\s+['\"]?[A-Za-z0-9_./+=-]{16,}['\"]?", re.IGNORECASE)
VARIABLE_BEARER_RE = re.compile(
    r"bearer[^\n]*(?:\{[^}\n]+\}|\$\{[^}\n]+\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|\+\s*[A-Za-z_][A-Za-z0-9_]*|process\.env\.|os\.environ|os\.getenv|api_?token|token)",
    re.IGNORECASE,
)


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _key_text(key: SentinelKey) -> str:
    return f"{key[0]}:{key[1]} {key[2]}"


def _sentinel_key(sentinel: Any) -> SentinelKey:
    return (
        str(getattr(sentinel, "path", "") or ""),
        _line_number(getattr(sentinel, "line", 0)),
        v5._sentinel_kind(sentinel),
    )


def _finding_line(finding: dict[str, Any]) -> int:
    return _line_number(finding.get("line", 0))


def _finding_path(finding: dict[str, Any]) -> str:
    return str(finding.get("path", "") or "")


def _finding_public_text(finding: dict[str, Any]) -> str:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    parts = [
        str(finding.get("title", "") or ""),
        str(finding.get("body", "") or ""),
        str(finding.get("validation", "") or ""),
        str(guidance.get("notes", "") or ""),
        str(guidance.get("remove", "") or ""),
        str(guidance.get("replace", "") or ""),
        str(guidance.get("add", "") or ""),
    ]
    return v5._normalize("\n".join(parts))


def _kind_text_matches(kind: str, finding: dict[str, Any], sentinel_text: str) -> bool:
    text = _finding_public_text(finding)
    line = str(sentinel_text or "")
    line_norm = v5._normalize(line)
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return "pull_request_target" in text or "pull_request_target" in line_norm
    if kind == v4.YAML_BROAD_WRITE:
        return (
            ("write" in text and ("permission" in text or "token" in text or "pull-requests" in text or "write access" in text))
            or bool(v4.WRITE_PERMISSION_RE.search(line))
        )
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return "checkout" in text and ("untrusted" in text or "head.ref" in text or "head sha" in text or "pull request head" in text or "pr head" in text)
    if kind == v4.YAML_SHELL_PIPE:
        return (("curl" in text or "wget" in text or "network" in text) and ("bash" in text or " sh" in text or "pipe" in text or "|" in text)) or bool(v4.SHELL_PIPE_RE.search(line))
    if kind == v4.YAML_METADATA_SHELL:
        return (("metadata" in text or "pr title" in text or "pull request title" in text or "github.event.pull_request" in text) and ("shell" in text or "command" in text or "bash" in text or " sh" in text)) or v4._metadata_shell_line(line)
    if kind == v4.PS_ACL:
        return "acl" in text or "filesystemaccessrule" in text or "fullcontrol" in text or "set-acl" in text or bool(v4.PS_ACL_RE.search(line))
    if kind == v4.PS_PROCESS_LAUNCH:
        return "start-process" in text or "process launch" in text or "executable" in text or bool(v4.PS_START_PROCESS_RE.search(line))
    if kind == v5.PS_ENV_TOKEN:
        return ("environment token" in text or "dcoir_token" in text or "$env:" in text) and ("callback" in text or "authorization" in text or "invoke-restmethod" in text or "invoke-webrequest" in text or "request-controlled" in text)
    if kind == v5.PYTHON_ENV_TOKEN:
        return ("environment token" in text or "dcoir_token" in text or "os.getenv" in text or "os.environ" in text) and ("callback" in text or "authorization" in text or "requests." in text or "request-controlled" in text)
    if kind == v5.PYTHON_YAML_LOAD:
        return "yaml.load" in text or "yaml.loader" in text or "unsafe yaml" in text or "deserialization" in text
    if kind == v5.PYTHON_SHELL_EXEC:
        return "shell=true" in text or ("subprocess" in text and "shell" in text)
    return v5._semantic_kind(finding) == kind


def _same_required_site(finding: dict[str, Any], sentinel: Any) -> bool:
    kind = v5._sentinel_kind(sentinel)
    if _finding_path(finding) != str(getattr(sentinel, "path", "") or ""):
        return False
    return v5._coverage_line(kind, _finding_line(finding), _line_number(getattr(sentinel, "line", 0)))


def _covers_required_sentinel(finding: dict[str, Any], sentinel: Any, original_covers: Any | None = None) -> bool:
    key = _sentinel_key(sentinel)
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and tuple(explicit) == key:
        return True
    if v5.finding_covers_sentinel(finding, sentinel, original_covers):
        return True
    if not _same_required_site(finding, sentinel):
        return False
    return _kind_text_matches(key[2], finding, str(getattr(sentinel, "text", "") or ""))


def _annotate_required_finding(finding: dict[str, Any], sentinel: Any) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    item = dict(finding)
    item.setdefault("_anchored_line_text", str(getattr(sentinel, "text", "") or ""))
    item["_risk_sentinel_key"] = key
    item["_risk_sentinel_kind"] = key[2]
    normalized = v5._normalize_comment_finding(item)
    normalized["_risk_sentinel_key"] = key
    normalized["_risk_sentinel_kind"] = key[2]
    normalized.setdefault("_anchored_line_text", str(getattr(sentinel, "text", "") or ""))
    return normalized


def _required_fallback(sentinel: Any, config: Any, original_fallback: Any | None = None) -> dict[str, Any]:
    finding = v5._fallback_finding(sentinel, config, original_fallback)
    if not finding:
        return finding
    return _annotate_required_finding(finding, sentinel)


def _postable_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
        return str(explicit[0]), _line_number(explicit[1]), str(explicit[2])
    normalized = v5._normalize_comment_finding(finding)
    return _finding_path(normalized), _finding_line(normalized), v5._semantic_kind(normalized) or str(normalized.get("title", "") or "")


def _dedupe_postable(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    order: list[tuple[str, int, str]] = []
    for finding in findings:
        key = _postable_key(finding)
        if key not in by_key:
            by_key[key] = finding
            order.append(key)
            continue
        if float(finding.get("confidence", 0) or 0) >= float(by_key[key].get("confidence", 0) or 0):
            by_key[key] = finding
    return [by_key[key] for key in order]
