"""Deterministic hashing and file-identity helpers for DCOIR Review v42."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from dcoir_review_required_runtime_patch_v41_review_state import (
    ARCHITECTURE_CONTRACT,
    PROVENANCE_PREFIX,
)
from dcoir_review_required_runtime_patch_v42_contract import (
    SEMANTIC_LEDGER_CONTRACT,
)


def normalized(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): normalized(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [normalized(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return str(value)


def digest(value: Any) -> str:
    payload = json.dumps(
        normalized(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def text_digest(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def config_snapshot(config: Any) -> dict[str, Any]:
    try:
        raw = vars(config)
    except TypeError:
        raw = {}
    return {
        str(key): normalized(value)
        for key, value in sorted(raw.items())
        if not str(key).startswith("_") and not callable(value)
    }


def valid_blob_sha(value: str) -> bool:
    candidate = value.strip().lower()
    return len(candidate) in {40, 64} and all(
        character in "0123456789abcdef" for character in candidate
    )


def semantic_context_summary(value: Any) -> str:
    """Remove v41's per-run publication receipt from semantic identity."""

    text = str(value or "").strip()
    marker_index = text.rfind(PROVENANCE_PREFIX)
    if marker_index < 0:
        return text
    return text[:marker_index].rstrip(" ;")


def file_record(
    item: dict[str, Any],
    *,
    schema_sha256: str,
    config_sha256: str,
    dependency_sha256: str,
) -> dict[str, Any]:
    path = str(item.get("filename", "") or "").replace("\\", "/").strip()
    status = str(item.get("status", "") or "").strip().lower()
    blob_sha = str(item.get("sha", "") or "").strip().lower()
    deleted = status in {"removed", "deleted"}
    content_identity_available = deleted or valid_blob_sha(blob_sha)
    content_identity = (
        f"deleted:{path}"
        if deleted
        else (f"github-blob:{blob_sha}" if valid_blob_sha(blob_sha) else "")
    )
    base_record = {
        "path": path,
        "previous_path": str(item.get("previous_filename", "") or "")
        .replace("\\", "/")
        .strip(),
        "status": status,
        "blob_sha": blob_sha if valid_blob_sha(blob_sha) else "",
        "content_identity_available": content_identity_available,
        "content_identity": content_identity,
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
        "patch_sha256": text_digest(item.get("patch", ""))
        if item.get("patch")
        else "",
    }
    record = dict(base_record)
    record["surface_fingerprint"] = digest(base_record)
    record["prospective_reuse_key"] = (
        digest(
            {
                "contract": SEMANTIC_LEDGER_CONTRACT,
                "architecture": ARCHITECTURE_CONTRACT,
                "schema_sha256": schema_sha256,
                "config_sha256": config_sha256,
                "dependency_sha256": dependency_sha256,
                "path": path,
                "content_identity": content_identity,
            }
        )
        if content_identity_available
        else ""
    )
    # v42 defines and measures the key but deliberately does not consume prior
    # semantic results. Dependency-aware invalidation is not enabled yet.
    record["reuse_allowed"] = False
    return record


def line_index_digest(line_index: dict[tuple[str, int], int]) -> str:
    rows = [
        [str(path), int(line), int(position)]
        for (path, line), position in sorted(
            line_index.items(), key=lambda pair: (str(pair[0][0]), int(pair[0][1]))
        )
    ]
    return digest(rows)


__all__ = [
    "config_snapshot",
    "digest",
    "file_record",
    "line_index_digest",
    "normalized",
    "semantic_context_summary",
    "text_digest",
    "valid_blob_sha",
]
