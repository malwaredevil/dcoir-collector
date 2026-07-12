"""Eleventh required-coverage layer for DCOIR Review.

This connector-safe layer fixes the #335 selection failure without editing the
large reviewer script. It keeps v10's overflow behavior, then adds:

- primary semantic kind validation separate from contextual explanatory kinds
- blank-kind backfills for Python archive/path writes and Kubernetes pressure
- Python archive coalescing to the extractall sink line
- balanced required selection across YAML, Python, and PowerShell
- split required/optional overflow metadata for debug/progress readback
"""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v8 as v8
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v10 as v10

SentinelKey = tuple[str, int, str]

PYTHON_ARCHIVE_EXTRACT = "python_archive_extract"
PYTHON_PATH_WRITE = "python_path_write"
K8S_HOST_NETWORK = "k8s_host_network"
K8S_PRIVILEGED_CONTAINER = "k8s_privileged_container"
K8S_PRIVILEGE_ESCALATION = "k8s_privilege_escalation"
K8S_HOST_PATH = "k8s_host_path"

YAML_KIND_ORDER = {
    v10.YAML_TOKEN_TO_PR_URL: 0,
    v4.YAML_SHELL_PIPE: 1,
    v4.YAML_PULL_REQUEST_TARGET: 2,
    v4.YAML_UNTRUSTED_CHECKOUT: 3,
    v4.YAML_METADATA_SHELL: 4,
    v4.YAML_BROAD_WRITE: 5,
}
PYTHON_KIND_ORDER = {
    v9.PYTHON_PICKLE_LOAD: 0,
    v5.PYTHON_YAML_LOAD: 1,
    v5.PYTHON_SHELL_EXEC: 2,
    v5.PYTHON_ENV_TOKEN: 3,
    PYTHON_ARCHIVE_EXTRACT: 4,
    PYTHON_PATH_WRITE: 5,
}
POWERSHELL_KIND_ORDER = {
    v9.PS_DYNAMIC_EXEC: 0,
    v4.PS_ACL: 1,
    v4.PS_PROCESS_LAUNCH: 2,
    v5.PS_ENV_TOKEN: 3,
}
K8S_KIND_ORDER = {
    K8S_HOST_NETWORK: 0,
    K8S_PRIVILEGED_CONTAINER: 1,
    K8S_PRIVILEGE_ESCALATION: 2,
    K8S_HOST_PATH: 3,
}

PYTHON_PATH_WRITE_RE = re.compile(
    r"\.(?:write_text|write_bytes)\s*\("
    r"|\bopen\s*\([^\n)]*,\s*['\"][^'\"]*(?:[wax]|r\+)[^'\"]*['\"]"
    r"|\bopen\s*\([^\n)]*\bmode\s*=\s*['\"][^'\"]*(?:[wax]|r\+)[^'\"]*['\"]"
    r"|\.open\s*\(\s*(?:mode\s*=\s*)?['\"][^'\"]*(?:[wax]|r\+)[^'\"]*['\"]",
    re.I,
)


def _normalize(value: Any) -> str:
    return v5._normalize(value)


def _canonical_kind(kind: str) -> str:
    if kind == getattr(v4, "PS_OUTBOUND_TOKEN", "ps_outbound_token"):
        return v5.PS_ENV_TOKEN
    return str(kind or "")


def _key_text(key: SentinelKey) -> str:
    return f"{key[0]}:{key[1]} {key[2]}"


def _base_line_kind(path: str, text: str) -> str:
    original = getattr(core, "_dcoir_required_v11_original_line_kind", None)
    if callable(original):
        return original(path, text)
    return core._line_kind(path, text)


def _base_semantic_kind(finding: dict[str, Any]) -> str:
    original = getattr(core, "_dcoir_required_v11_original_semantic_kind", None)
    if callable(original):
        return original(finding)
    return ""


def _base_sentinel_key(sentinel: Any) -> SentinelKey:
    original = getattr(core, "_dcoir_required_v11_original_sentinel_key", None)
    if callable(original):
        return original(sentinel)
    return "", 0, ""


def _base_required_sentinels(hardened: Any, risk_sentinels: list[Any]) -> list[Any]:
    original = getattr(core, "_dcoir_required_v11_original_required_sentinels", None)
    if callable(original):
        return list(original(hardened, risk_sentinels))
    return list(core._required_sentinels(hardened, risk_sentinels))


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    line = str(text or "")
    lowered = _normalize(line)
    base_kind = _base_line_kind(path, text)
    if base_kind:
        return _canonical_kind(base_kind)
    if suffix == ".py":
        if re.search(r"\.extractall\s*\(", line):
            return PYTHON_ARCHIVE_EXTRACT
        if re.search(r"\btarfile\.open\s*\(", line) and "extract" in lowered:
            return PYTHON_ARCHIVE_EXTRACT
        if PYTHON_PATH_WRITE_RE.search(line):
            return PYTHON_PATH_WRITE
    if suffix in {".yml", ".yaml"}:
        workflow_token_to_pr_url = getattr(v10, "_workflow_token_to_pr_url", None)
        workflow_pr_label_shell = getattr(v10, "_workflow_pr_label_shell", None)
        if callable(workflow_token_to_pr_url) and workflow_token_to_pr_url(line):
            return v10.YAML_TOKEN_TO_PR_URL
        if (
            ("secrets.github_token" in lowered or "authorization" in lowered or "bearer" in lowered)
            and ("github.event.pull_request.body" in lowered or "pull_request.body" in lowered)
        ):
            return v10.YAML_TOKEN_TO_PR_URL
        if callable(workflow_pr_label_shell) and workflow_pr_label_shell(line):
            return v4.YAML_METADATA_SHELL
        if "github.event.pull_request.labels" in lowered and any(
            token in lowered for token in ("bash", " sh ", "sh -c", "pwsh", "powershell", "-lc", "-c")
        ):
            return v4.YAML_METADATA_SHELL
        if re.search(r"\bhostNetwork\s*:\s*true\b", line, re.I):
            return K8S_HOST_NETWORK
        if re.search(r"\bprivileged\s*:\s*true\b", line, re.I):
            return K8S_PRIVILEGED_CONTAINER
        if re.search(r"\ballowPrivilegeEscalation\s*:\s*true\b", line, re.I):
            return K8S_PRIVILEGE_ESCALATION
        if re.search(r"\bhostPath\s*:", line, re.I):
            return K8S_HOST_PATH
    return ""


def _text_kinds(path: str, text: str) -> set[str]:
    suffix = Path(str(path or "").lower()).suffix
    lowered = _normalize(text)
    kinds = set(core._claimed_kinds({"path": path, "title": text, "body": "", "description": ""}))
    if suffix == ".py":
        if "extractall" in lowered or ("tarfile" in lowered and "extract" in lowered):
            kinds.add(PYTHON_ARCHIVE_EXTRACT)
        if PYTHON_PATH_WRITE_RE.search(str(text or "")):
            kinds.add(PYTHON_PATH_WRITE)
    if suffix in {".yml", ".yaml"}:
        if "hostnetwork" in lowered:
            kinds.add(K8S_HOST_NETWORK)
        if "privileged" in lowered:
            kinds.add(K8S_PRIVILEGED_CONTAINER)
        if "allowprivilegeescalation" in lowered:
            kinds.add(K8S_PRIVILEGE_ESCALATION)
        if "hostpath" in lowered:
            kinds.add(K8S_HOST_PATH)
    return {_canonical_kind(item) for item in kinds if item}


def _title_kinds(finding: dict[str, Any]) -> set[str]:
    return _text_kinds(str(finding.get("path", "") or ""), str(finding.get("title", "") or ""))


def _contextual_kinds(finding: dict[str, Any]) -> set[str]:
    path = str(finding.get("path", "") or "")
    text = "\n".join(
        str(finding.get(name, "") or "")
        for name in ("title", "body", "description", "_anchored_line_text", "suggested_replacement")
    )
    return _text_kinds(path, text)


def _explicit_kind(finding: dict[str, Any]) -> str:
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
        return _canonical_kind(str(explicit[2]))
    return _canonical_kind(str(finding.get("_risk_sentinel_kind", "") or ""))


def _primary_kind(finding: dict[str, Any], allowed: set[str] | None = None) -> str:
    explicit = _explicit_kind(finding)
    if explicit:
        return explicit
    path = str(finding.get("path", "") or "")
    anchor_kind = _line_kind(path, str(finding.get("_anchored_line_text", "") or ""))
    if anchor_kind:
        return anchor_kind
    titles = _title_kinds(finding)
    if allowed:
        matches = sorted(titles & allowed, key=lambda item: _kind_rank(item))
        if matches:
            return matches[0]
    if titles:
        return sorted(titles, key=lambda item: _kind_rank(item))[0]
    return ""


def _semantic_kind(finding: dict[str, Any]) -> str:
    return _primary_kind(finding) or _base_semantic_kind(finding)


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    path = str(finding.get("path", "") or "")
    return path, core._line_number(finding.get("line", 0)), _semantic_kind(finding)


def _sentinel_key(sentinel: Any) -> SentinelKey:
    path = str(getattr(sentinel, "path", "") or "")
    line = core._line_number(getattr(sentinel, "line", 0))
    text = str(getattr(sentinel, "text", "") or "")
    label = str(getattr(sentinel, "label", "") or "")
    detail = str(getattr(sentinel, "detail", "") or "")
    kind = _line_kind(path, text) or _base_sentinel_key(sentinel)[2]
    context = f"{text}\n{label}\n{detail}"
    if not kind:
        kinds = _text_kinds(path, context)
        kind = sorted(kinds, key=lambda item: _kind_rank(item))[0] if kinds else ""
    return path, line, _canonical_kind(kind)


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind == v4.YAML_BROAD_WRITE:
        return path, 0, kind
    if kind == PYTHON_ARCHIVE_EXTRACT:
        return path, 0, kind
    return path, line, kind


def _family(kind: str) -> str:
    if kind.startswith("yaml_"):
        return "yaml"
    if kind.startswith("python_"):
        return "python"
    if kind.startswith("ps_"):
        return "powershell"
    if kind.startswith("k8s_"):
        return "kubernetes"
    return "other"


def _kind_rank(kind: str) -> int:
    if kind in YAML_KIND_ORDER:
        return YAML_KIND_ORDER[kind]
    if kind in PYTHON_KIND_ORDER:
        return PYTHON_KIND_ORDER[kind]
    if kind in POWERSHELL_KIND_ORDER:
        return POWERSHELL_KIND_ORDER[kind]
    if kind in K8S_KIND_ORDER:
        return 40 + K8S_KIND_ORDER[kind]
    return 99


def _sentinel_sort_key(sentinel: Any) -> tuple[int, str, int, str]:
    path, line, kind = _sentinel_key(sentinel)
    bonus = 0
    if kind == PYTHON_ARCHIVE_EXTRACT and "extractall" not in _normalize(getattr(sentinel, "text", "")):
        bonus = 1
    return _kind_rank(kind) + bonus, path, line, str(getattr(sentinel, "text", "") or "")


def _coalesce_required(required: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    targets: list[Any] = []
    seen: set[SentinelKey] = set()
    duplicates: list[dict[str, Any]] = []
    for sentinel in sorted(required, key=_sentinel_sort_key):
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in seen:
            duplicates.append(_sentinel_record(sentinel, "duplicate_covered", required=set(), selected=set(), limit=0))
            continue
        seen.add(coverage)
        targets.append(sentinel)
    return targets, duplicates


def _required_sentinels(hardened: Any, risk_sentinels: list[Any]) -> list[Any]:
    required = _base_required_sentinels(hardened, risk_sentinels)
    seen = {_sentinel_key(item) for item in required}
    for sentinel in risk_sentinels:
        key = _sentinel_key(sentinel)
        kind = key[2]
        if kind in {
            v10.YAML_TOKEN_TO_PR_URL,
            v4.YAML_METADATA_SHELL,
            v4.YAML_SHELL_PIPE,
            v4.YAML_PULL_REQUEST_TARGET,
            v4.YAML_UNTRUSTED_CHECKOUT,
            v4.YAML_BROAD_WRITE,
            v9.PYTHON_PICKLE_LOAD,
            v5.PYTHON_YAML_LOAD,
            v5.PYTHON_SHELL_EXEC,
            v5.PYTHON_ENV_TOKEN,
            PYTHON_ARCHIVE_EXTRACT,
            PYTHON_PATH_WRITE,
            v9.PS_DYNAMIC_EXEC,
            v4.PS_ACL,
            v4.PS_PROCESS_LAUNCH,
            v5.PS_ENV_TOKEN,
        } and key not in seen:
            required.append(sentinel)
            seen.add(key)
    return required


def _expected_by_line(hardened: Any, risk_sentinels: list[Any]) -> dict[tuple[str, int], set[str]]:
    expected: dict[tuple[str, int], set[str]] = {}
    for sentinel in _required_sentinels(hardened, risk_sentinels):
        path, line, kind = _sentinel_key(sentinel)
        expected.setdefault((path, line), set()).add(kind)
    return expected


def _semantic_mismatch(finding: dict[str, Any], expected: dict[tuple[str, int], set[str]]) -> bool:
    path = str(finding.get("path", "") or "")
    line = core._line_number(finding.get("line", 0))
    allowed = expected.get((path, line), set())
    if not allowed:
        return False
    explicit = _explicit_kind(finding)
    if explicit and explicit not in allowed:
        return True
    if explicit:
        return False
    title_kinds = _title_kinds(finding)
    if title_kinds and not (title_kinds & allowed):
        return True
    primary = _primary_kind(finding, allowed)
    if not primary:
        return True
    return primary not in allowed


def _dedupe(findings: list[dict[str, Any]], expected: dict[tuple[str, int], set[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: dict[SentinelKey, dict[str, Any]] = {}
    order: list[SentinelKey] = []
    dropped: list[str] = []
    for finding in findings:
        item = v5._normalize_comment_finding(finding)
        key = _postable_key(item)
        if _semantic_mismatch(item, expected):
            dropped.append(f"{key[0]}:{key[1]} expected={','.join(sorted(expected.get((key[0], key[1]), set())))} actual={key[2]}")
            continue
        if not key[2]:
            dropped.append(f"{key[0]}:{key[1]} empty semantic kind")
            continue
        if key not in kept:
            kept[key] = item
            order.append(key)
            continue
        dropped.append(f"{key[0]}:{key[1]} duplicate {key[2]}")
        if (core._severity_rank(item), -core._confidence(item)) < (
            core._severity_rank(kept[key]),
            -core._confidence(kept[key]),
        ):
            kept[key] = item
    return [kept[key] for key in order], dropped


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, int, float, str, int]:
    path, line, kind = _postable_key(finding)
    optional = "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_")
    family_rank = {"yaml": 0, "powershell": 1, "python": 2, "kubernetes": 4, "other": 5}.get(_family(kind), 5)
    if optional:
        family_rank += 5
    return family_rank, _kind_rank(kind), core._severity_rank(finding), -core._confidence(finding), path, line


def _bucket_required_targets(targets: list[Any]) -> dict[str, list[Any]]:
    buckets: dict[str, list[Any]] = {}
    for sentinel in targets:
        buckets.setdefault(_family(_sentinel_key(sentinel)[2]), []).append(sentinel)
    for family, values in buckets.items():
        buckets[family] = sorted(values, key=_sentinel_sort_key)
    return buckets


def _balanced_required_order(targets: list[Any]) -> list[Any]:
    buckets = _bucket_required_targets(targets)
    order: list[Any] = []
    family_order = ["yaml", "powershell", "python", "other", "kubernetes"]
    while any(buckets.get(family) for family in family_order):
        for family in family_order:
            bucket = buckets.get(family) or []
            if bucket:
                order.append(bucket.pop(0))
    return order
