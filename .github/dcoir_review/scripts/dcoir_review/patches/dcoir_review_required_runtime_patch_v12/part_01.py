"""Twelfth required-coverage layer for DCOIR Review.

This connector-safe layer fixes the #336 selection/ledger failure without
editing the large reviewer script. It keeps v11's public rendering behavior,
then adds:

- deterministic Python archive/path-write sentinel insertion
- deterministic fallback for privileged untrusted checkout
- post-suppression required backfill so inline budget is not wasted
- final ledger accounting for every detected required sentinel
- same-line Python env-token/SSRF coalescing for callback sinks
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v9_selection as selection
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11

SentinelKey = tuple[str, int, str]

VERSION = "v12"


def _preserve_v11_helper(name: str) -> Any:
    storage_name = f"_dcoir_required_v12_original_{name.lstrip('_')}"
    existing = getattr(v11, storage_name, None)
    if callable(existing):
        return existing
    helper = getattr(v11, name)
    setattr(v11, storage_name, helper)
    return helper


_ORIGINAL_V11_POSTABLE_KEY = _preserve_v11_helper("_postable_key")
_ORIGINAL_V11_VALIDATION_FOR_KEY = _preserve_v11_helper("_validation_for_key")
REQUIRED_KINDS = {
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
    v11.PYTHON_ARCHIVE_EXTRACT,
    v11.PYTHON_PATH_WRITE,
    v9.PS_DYNAMIC_EXEC,
    v4.PS_ACL,
    v4.PS_PROCESS_LAUNCH,
    v5.PS_ENV_TOKEN,
}


def _canonical_kind(kind: str, text: str = "", detail: str = "") -> str:
    value = str(kind or "")
    context = v11._normalize(f"{text}\n{detail}")
    if value == getattr(v4, "PYTHON_SSRF", "python_ssrf"):
        has_token_source = "dcoir_token" in context or "os.environ" in context or "os.getenv" in context
        has_auth_token = "authorization" in context and ("bearer" in context or "token" in context)
        has_callback = (
            "callback" in context
            or "requests." in context
            or "request-controlled" in context
        )
        if has_callback and (has_token_source or has_auth_token):
            return v5.PYTHON_ENV_TOKEN
    return v11._canonical_kind(value)


def _sentinel_key(sentinel: Any) -> SentinelKey:
    path = str(getattr(sentinel, "path", "") or "")
    line = core._line_number(getattr(sentinel, "line", 0))
    text = str(getattr(sentinel, "text", "") or "")
    detail = "\n".join(str(getattr(sentinel, name, "") or "") for name in ("label", "detail"))
    kind = v11._line_kind(path, text) or v11._base_sentinel_key(sentinel)[2]
    if not kind:
        kinds = v11._text_kinds(path, f"{text}\n{detail}")
        kind = sorted(kinds, key=lambda item: _kind_rank(item))[0] if kinds else ""
    return path, line, _canonical_kind(kind, text, detail)


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    path, line, kind = _ORIGINAL_V11_POSTABLE_KEY(finding)
    text = "\n".join(
        str(finding.get(name, "") or "")
        for name in ("title", "body", "description", "_anchored_line_text")
    )
    return path, line, _canonical_kind(kind, text, text)


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind == v4.YAML_BROAD_WRITE:
        return path, 0, kind
    if kind == v11.PYTHON_ARCHIVE_EXTRACT:
        return path, 0, kind
    return path, line, kind


def _kind_rank(kind: str) -> int:
    order = {
        v10.YAML_TOKEN_TO_PR_URL: 0,
        v4.YAML_SHELL_PIPE: 1,
        v4.YAML_UNTRUSTED_CHECKOUT: 2,
        v4.YAML_METADATA_SHELL: 3,
        v4.YAML_PULL_REQUEST_TARGET: 4,
        v4.YAML_BROAD_WRITE: 5,
        v9.PS_DYNAMIC_EXEC: 10,
        v4.PS_ACL: 11,
        v4.PS_PROCESS_LAUNCH: 12,
        v5.PS_ENV_TOKEN: 13,
        v9.PYTHON_PICKLE_LOAD: 20,
        v5.PYTHON_YAML_LOAD: 21,
        v5.PYTHON_SHELL_EXEC: 22,
        v5.PYTHON_ENV_TOKEN: 23,
        v11.PYTHON_ARCHIVE_EXTRACT: 24,
        v11.PYTHON_PATH_WRITE: 25,
        v11.K8S_HOST_NETWORK: 40,
        v11.K8S_PRIVILEGED_CONTAINER: 41,
        v11.K8S_PRIVILEGE_ESCALATION: 42,
        v11.K8S_HOST_PATH: 43,
    }
    return order.get(str(kind or ""), 99)


def _sentinel_sort_key(sentinel: Any) -> tuple[int, str, int, str]:
    path, line, kind = _sentinel_key(sentinel)
    text = str(getattr(sentinel, "text", "") or "")
    bonus = 1 if kind == v11.PYTHON_ARCHIVE_EXTRACT and "extractall" not in v11._normalize(text) else 0
    return _kind_rank(kind) + bonus, path, line, text


def _family(kind: str) -> str:
    if kind.startswith("yaml_"):
        return "yaml"
    if kind.startswith("ps_"):
        return "powershell"
    if kind.startswith("python_"):
        return "python"
    if kind.startswith("k8s_"):
        return "kubernetes"
    return "other"


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, int, float, str, int]:
    path, line, kind = _postable_key(finding)
    optional = "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_")
    family_rank = {"yaml": 0, "powershell": 1, "python": 2, "kubernetes": 4, "other": 5}.get(_family(kind), 5)
    if optional:
        family_rank += 5
    return family_rank, _kind_rank(kind), core._severity_rank(finding), -core._confidence(finding), path, line


def _required_sentinels(hardened: Any, risk_sentinels: list[Any]) -> list[Any]:
    required: list[Any] = []
    seen: set[SentinelKey] = set()
    for sentinel in v11._base_required_sentinels(hardened, risk_sentinels):
        key = _sentinel_key(sentinel)
        if key[2] in REQUIRED_KINDS and key not in seen:
            required.append(sentinel)
            seen.add(key)
    for sentinel in risk_sentinels:
        key = _sentinel_key(sentinel)
        if key[2] in REQUIRED_KINDS and key not in seen:
            required.append(sentinel)
            seen.add(key)
    return required


def _coalesce_required(required: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    targets: list[Any] = []
    seen: set[SentinelKey] = set()
    duplicates: list[dict[str, Any]] = []
    for sentinel in sorted(required, key=_sentinel_sort_key):
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in seen:
            duplicates.append(_sentinel_record(sentinel, "duplicate_covered", set(), set(), 0))
            continue
        seen.add(coverage)
        targets.append(sentinel)
    return targets, duplicates


def _expected_by_line(hardened: Any, risk_sentinels: list[Any]) -> dict[tuple[str, int], set[str]]:
    expected: dict[tuple[str, int], set[str]] = {}
    for sentinel in _required_sentinels(hardened, risk_sentinels):
        path, line, kind = _sentinel_key(sentinel)
        expected.setdefault((path, line), set()).add(kind)
    return expected


def _semantic_mismatch(finding: dict[str, Any], expected: dict[tuple[str, int], set[str]]) -> bool:
    path, line, kind = _postable_key(finding)
    allowed = expected.get((path, line), set())
    if not allowed:
        return False
    explicit = v11._explicit_kind(finding)
    if explicit and _canonical_kind(explicit) not in allowed:
        return True
    title_kinds = v11._title_kinds(finding)
    if title_kinds and not ({_canonical_kind(item) for item in title_kinds} & allowed):
        return True
    return kind not in allowed


def _fallback_for_sentinel(hardened: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    path, line, kind = key
    line_text = str(getattr(sentinel, "text", "") or "")
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        fallback = {
            "title": "Privileged workflow checks out untrusted PR code",
            "severity": "critical",
            "confidence": 0.99,
            "path": path,
            "line": line,
            "body": (
                "This privileged workflow checks out pull request controlled code. "
                "Do not combine `pull_request_target` privileges with PR-controlled refs or head SHAs."
            ),
            "suggested_replacement": "",
            "validation": _validation_for_key(kind, path, line),
            "fix_guidance": {
                "language": "yaml",
                "notes": "Use a trusted base ref, or split privileged metadata handling from untrusted code checkout/execution.",
                "validation": _validation_for_key(kind, path, line),
            },
        }
    else:
        fallback = v11._fallback_for_sentinel(hardened, sentinel, config)
    fallback["_risk_sentinel_key"] = [path, line, kind]
    fallback["_risk_sentinel_kind"] = kind
    fallback["_anchored_line_text"] = line_text
    return fallback


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    if kind == v10.YAML_TOKEN_TO_PR_URL:
        return v10._validation_for_token_to_pr_url(path)
    return _ORIGINAL_V11_VALIDATION_FOR_KEY(kind, path, line)


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


def _balanced_required_order(targets: list[Any]) -> list[Any]:
    buckets: dict[str, list[Any]] = {}
    for sentinel in targets:
        buckets.setdefault(_family(_sentinel_key(sentinel)[2]), []).append(sentinel)
    for family, values in list(buckets.items()):
        buckets[family] = sorted(values, key=_sentinel_sort_key)
    result: list[Any] = []
    family_order = ["yaml", "powershell", "python", "other", "kubernetes"]
    while any(buckets.get(family) for family in family_order):
        for family in family_order:
            bucket = buckets.get(family) or []
            if bucket:
                result.append(bucket.pop(0))
    return result


def _fallback_candidate(
    hardened: Any,
    sentinel: Any,
    config: Any,
    expected: dict[tuple[str, int], set[str]],
) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    fallback = _fallback_for_sentinel(hardened, sentinel, config)
    normalized = dict(fallback) if fallback.get("_dcoir_v9_known_fallback") or fallback.get("_dcoir_v10_known_fallback") else v5._normalize_comment_finding(fallback)
    normalized["_risk_sentinel_key"] = list(key)
    normalized["_risk_sentinel_kind"] = key[2]
    normalized["_anchored_line_text"] = str(getattr(sentinel, "text", "") or "")
    if _semantic_mismatch(normalized, expected):
        # Keep the deterministic fallback authoritative even if an older normalizer
        # tries to infer a contextual title from surrounding text.
        normalized["title"] = str(fallback.get("title") or str(getattr(sentinel, "label", "") or key[2]))
        normalized["body"] = str(fallback.get("body") or str(getattr(sentinel, "detail", "") or "Required changed-line risk."))
    return normalized
