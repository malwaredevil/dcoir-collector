"""Fourteenth required-coverage layer for DCOIR Review.

This connector-safe overlay fixes the #339 live-test regression without
rewriting the large reviewer script. v13 made semantic titles much better, but
it still allowed adjacent duplicate findings to consume budget, let Python be
starved under required-risk pressure, and preserved validation text that
belonged to a different semantic kind. v14 tightens those final-stage gates.
"""

from __future__ import annotations

import re
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v12 as v12
import dcoir_review_required_runtime_patch_v13 as v13

SentinelKey = tuple[str, int, str]

VERSION = "v14"
FAMILY_ORDER = ("yaml", "powershell", "python", "other", "kubernetes", "typescript")
SELECTION_KIND_RANK = {
    v10.YAML_TOKEN_TO_PR_URL: 0,
    v4.YAML_METADATA_SHELL: 1,
    v4.YAML_SHELL_PIPE: 2,
    v4.YAML_UNTRUSTED_CHECKOUT: 3,
    v4.YAML_PULL_REQUEST_TARGET: 10,
    v4.YAML_BROAD_WRITE: 11,
    v9.PS_DYNAMIC_EXEC: 0,
    v4.PS_PROCESS_LAUNCH: 1,
    v5.PS_ENV_TOKEN: 2,
    v4.PS_ACL: 3,
    v9.PYTHON_PICKLE_LOAD: 0,
    v5.PYTHON_SHELL_EXEC: 1,
    v11.PYTHON_ARCHIVE_EXTRACT: 2,
    v11.PYTHON_PATH_WRITE: 3,
    v5.PYTHON_YAML_LOAD: 4,
    v5.PYTHON_ENV_TOKEN: 5,
    v13.K8S_HOST_PID: 0,
    v13.K8S_PRIVILEGED_CONTAINER: 1,
    v13.K8S_PRIVILEGE_ESCALATION: 2,
    v13.K8S_HOST_PATH: 3,
    v13.K8S_HOST_NETWORK: 4,
    v13.TS_INNER_HTML: 0,
    v13.TS_DYNAMIC_EXECUTION: 1,
}


def _missing_render_integrity_errors(_findings: list[dict[str, Any]], _expected: dict[tuple[str, int], set[str]]) -> list[str]:
    return []


def _preserve_v13_helper(name: str, fallback: Any = None) -> Any:
    storage_name = f"_dcoir_required_v14_original_{name.lstrip('_')}"
    existing = getattr(v13, storage_name, None)
    if callable(existing):
        return existing
    helper = getattr(v13, name, fallback)
    if not callable(helper):
        raise AttributeError(f"v13 helper {name} is unavailable and no callable fallback was provided")
    setattr(v13, storage_name, helper)
    return helper


_ORIGINAL_V13_COVERAGE_KEY = _preserve_v13_helper("_coverage_key")
_ORIGINAL_V13_SENTINEL_SORT_KEY = _preserve_v13_helper("_sentinel_sort_key")
_ORIGINAL_V13_BALANCED_REQUIRED_ORDER = _preserve_v13_helper("_balanced_required_order")
_ORIGINAL_V13_SPARE_PRIORITY = _preserve_v13_helper("_spare_priority")
_ORIGINAL_V13_SAFE_VALIDATION = _preserve_v13_helper("_safe_validation")
_ORIGINAL_V13_TEMPLATE_FOR_KIND = _preserve_v13_helper("_template_for_kind")
_ORIGINAL_V13_INTEGRITY_FINDING = _preserve_v13_helper("_integrity_finding")
_ORIGINAL_V13_RENDER_ERRORS = _preserve_v13_helper("_render_integrity_errors", _missing_render_integrity_errors)
_ORIGINAL_V13_RENDERED_PROBLEM = _preserve_v13_helper(
    "_rendered_comment_has_integrity_problem",
    getattr(v13, "_rendered_comment_has_problem", None),
)
_ORIGINAL_V13_AUGMENT_METADATA = _preserve_v13_helper("_augment_metadata")
_ORIGINAL_V13_SELECT_REQUIRED = _preserve_v13_helper("_select_required_postable")
_ORIGINAL_V13_PATCH_V12_GLOBALS = _preserve_v13_helper("_patch_v12_globals")
_ORIGINAL_V13_PATCH_CORE_SEMANTICS = _preserve_v13_helper("_patch_core_semantics")


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind in {v4.YAML_BROAD_WRITE, v4.PS_ACL, v11.PYTHON_ARCHIVE_EXTRACT, v13.K8S_HOST_PATH}:
        return path, 0, kind
    return _ORIGINAL_V13_COVERAGE_KEY(key)


def _sink_preference(kind: str, text: str) -> int:
    normalized = v13._normalize(text)
    if kind == v4.PS_ACL:
        if "set-acl" in normalized:
            return 0
        if "filesystemaccessrule" in normalized:
            return 1
        return 3
    if kind == v11.PYTHON_ARCHIVE_EXTRACT:
        if "extractall" in normalized:
            return 0
        if "tarfile.open" in normalized:
            return 2
        if "import tarfile" in normalized:
            return 5
        return 4
    if kind == v13.K8S_HOST_PATH:
        if "hostpath:" in normalized:
            return 0
        if "mountpath:" in normalized:
            return 4
        return 3
    return 0


def _sentinel_sort_key(sentinel: Any) -> tuple[int, int, str, int, str]:
    path, line, kind = v13._sentinel_key(sentinel)
    text = str(getattr(sentinel, "text", "") or "")
    return SELECTION_KIND_RANK.get(kind, v13._kind_rank(kind)), _sink_preference(kind, text), path, line, text


def _family(kind: str) -> str:
    return v12._family(kind)


def _spread_same_kind(values: list[Any]) -> list[Any]:
    by_kind: dict[str, list[Any]] = {}
    for sentinel in sorted(values, key=_sentinel_sort_key):
        by_kind.setdefault(v13._sentinel_key(sentinel)[2], []).append(sentinel)
    kinds = sorted(by_kind, key=lambda kind: SELECTION_KIND_RANK.get(kind, v13._kind_rank(kind)))
    result: list[Any] = []
    while any(by_kind.get(kind) for kind in kinds):
        for kind in kinds:
            bucket = by_kind.get(kind) or []
            if bucket:
                result.append(bucket.pop(0))
    return result


def _balanced_required_order(targets: list[Any]) -> list[Any]:
    buckets: dict[str, list[Any]] = {}
    for sentinel in targets:
        kind = v13._sentinel_key(sentinel)[2]
        buckets.setdefault(_family(kind), []).append(sentinel)
    for family, values in list(buckets.items()):
        buckets[family] = _spread_same_kind(values)
    ordered: list[Any] = []
    while any(buckets.get(family) for family in FAMILY_ORDER):
        for family in FAMILY_ORDER:
            bucket = buckets.get(family) or []
            if bucket:
                ordered.append(bucket.pop(0))
    for family in sorted(set(buckets) - set(FAMILY_ORDER)):
        ordered.extend(buckets.get(family) or [])
    return ordered


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, int, float, str, int]:
    path, line, kind = v13._postable_key(finding)
    optional_path = "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_")
    family_rank = {
        "yaml": 0,
        "powershell": 1,
        "python": 2,
        "other": 4,
        "kubernetes": 6,
        "typescript": 7,
    }.get(_family(kind), 8)
    if optional_path:
        family_rank += 6
    return family_rank, SELECTION_KIND_RANK.get(kind, v13._kind_rank(kind)), core._severity_rank(finding), -core._confidence(finding), path, line


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    return v13._validation_for_key(kind, path, line)


def _template_for_kind(kind: str) -> tuple[str, str, str]:
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return (
            "Privileged workflow checks out untrusted PR code",
            "This privileged workflow checks out pull request controlled code by using a PR-controlled ref or head SHA.",
            "Use a trusted base ref, or split privileged metadata handling from untrusted code checkout and execution.",
        )
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return (
            "Privileged pull request target workflow context",
            "This trigger runs with base-repository privileges. Keep untrusted pull request code and shell execution out of this workflow.",
            "Use an unprivileged pull request workflow for untrusted code paths, or limit this workflow to metadata-only operations.",
        )
    return _ORIGINAL_V13_TEMPLATE_FOR_KIND(kind)


def _safe_validation(kind: str, path: str, line: int, value: Any = "") -> str:
    if kind in v13.TRACKED_HIGH_RISK_KINDS:
        return _validation_for_key(kind, path, line)
    return _ORIGINAL_V13_SAFE_VALIDATION(kind, path, line, value)


def _looks_like_prose(value: str) -> bool:
    normalized = v13._normalize(value)
    return normalized.startswith(
        (
            "remove ",
            "replace ",
            "use ",
            "validate ",
            "the ",
            "if ",
            "this ",
            "set only ",
            "download ",
        )
    )
