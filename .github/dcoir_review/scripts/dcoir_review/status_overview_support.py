from __future__ import annotations

import base64
import hashlib
import html
import json
import zlib
from typing import Any

STATUS_METADATA_PREFIX = "<!-- dcoir-review-status-meta:v1:"
STATUS_METADATA_SUFFIX = " -->"
MAX_STATUS_METADATA_ENCODED_CHARS = 6000
MINIMAL_METADATA_KEYS = (
    "schema",
    "state",
    "pr_number",
    "reviewed_head_sha",
    "workflow_run_id",
    "workflow_run_url",
    "formal_review_id",
    "formal_review_url",
    "gate_status",
    "finding_count",
)


def _finding_line(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _digest_identity(*, path: Any, line: Any, title: Any, kind: Any = "") -> str:
    payload = {
        "kind": visible_text(kind).casefold()[:240],
        "line": _finding_line(line),
        "path": visible_text(path)[:500],
        "title": visible_text(title).casefold()[:200],
    }
    if not payload["path"] and not payload["title"] and not payload["kind"]:
        return ""
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"finding-digest:{digest[:32]}"


def _semantic_key_identity(value: Any) -> str:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return ""
    path = str(value[0] or "").strip()
    line = _finding_line(value[1])
    kind = str(value[2] or "").strip()
    if kind.startswith("semantic_candidate:"):
        candidate_id = kind.split("semantic_candidate:", 1)[1].strip()
        if candidate_id:
            return f"candidate-id:{candidate_id}"
    return _digest_identity(path=path, line=line, title="", kind=kind)


def _existing_identity(value: Any) -> str:
    identity = str(value or "").strip()
    if identity.startswith(("candidate-id:", "finding-digest:")):
        return identity
    if not identity.startswith("semantic-key:"):
        return ""
    payload = identity.split("semantic-key:", 1)[1]
    try:
        path, line_text, kind = payload.rsplit(":", 2)
    except ValueError:
        return ""
    if kind.startswith("semantic_candidate:"):
        candidate_id = kind.split("semantic_candidate:", 1)[1].strip()
        if candidate_id:
            return f"candidate-id:{candidate_id}"
    return _digest_identity(path=path, line=line_text, title="", kind=kind)


def canonical_finding_identity(finding: Any) -> str:
    if not isinstance(finding, dict):
        return ""
    existing = _existing_identity(finding.get("identity"))
    if existing:
        return existing
    candidate_id = str(finding.get("_dcoir_v51_candidate_id", "") or "").strip()
    if candidate_id:
        return f"candidate-id:{candidate_id}"
    semantic_key = _semantic_key_identity(finding.get("_dcoir_v51_semantic_candidate_key"))
    if semantic_key:
        return semantic_key
    return _digest_identity(
        path=finding.get("path", ""),
        line=finding.get("line", 0),
        title=finding.get("title", ""),
    )


def _encode_metadata_payload(metadata: dict[str, Any]) -> str:
    payload = json.dumps(
        metadata,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    return base64.b64encode(compressed).decode("ascii").rstrip("=")


def compact_metadata_finding(item: Any, normalize_severity: Any) -> dict[str, Any]:
    finding = item if isinstance(item, dict) else {}
    return {
        "identity": canonical_finding_identity(finding),
        "title": str(finding.get("title", "") or "")[:120],
        "severity": normalize_severity(finding.get("severity")),
        "path": str(finding.get("path", "") or "")[:160],
        "line": int(finding.get("line", 0) or 0),
        "url": str(finding.get("url", "") or "")[:240],
        "carried": bool(finding.get("carried", False)),
    }


def encode_status_metadata(metadata: dict[str, Any], normalize_severity: Any) -> str:
    bounded = dict(metadata)
    encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded["provenance_truncated"] = True
        bounded["open_findings"] = [
            compact_metadata_finding(item, normalize_severity)
            for item in bounded.get("open_findings", [])[:6]
        ]
        previous = bounded.get("previous_completed")
        if isinstance(previous, dict):
            bounded_previous = dict(previous)
            bounded_previous["open_findings"] = [
                compact_metadata_finding(item, normalize_severity)
                for item in bounded_previous.get("open_findings", [])[:6]
            ]
            bounded["previous_completed"] = bounded_previous
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded["open_findings"] = []
        previous = bounded.get("previous_completed")
        if isinstance(previous, dict):
            previous = dict(previous)
            previous["open_findings"] = []
            bounded["previous_completed"] = previous
        bounded["finding_detail_truncated"] = True
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded.pop("previous_completed", None)
        bounded["metadata_truncated"] = True
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded = {
            key: bounded.get(key)
            for key in MINIMAL_METADATA_KEYS
            if key in bounded
        }
        bounded["metadata_truncated"] = True
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded = {
            "schema": str(metadata.get("schema", "") or "")[:120],
            "state": str(metadata.get("state", "") or "")[:32],
            "pr_number": int(metadata.get("pr_number", 0) or 0),
            "reviewed_head_sha": str(metadata.get("reviewed_head_sha", "") or "")[:64],
            "finding_count": int(metadata.get("finding_count", 0) or 0),
            "metadata_truncated": True,
        }
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        encoded_metadata = _encode_metadata_payload({"metadata_truncated": True})
    return f"{STATUS_METADATA_PREFIX}{encoded_metadata}{STATUS_METADATA_SUFFIX}"


def parse_status_metadata(body: str) -> dict[str, Any]:
    text = str(body or "")
    start = text.find(STATUS_METADATA_PREFIX)
    if start < 0:
        return {}
    start += len(STATUS_METADATA_PREFIX)
    end = text.find(STATUS_METADATA_SUFFIX, start)
    if end < 0:
        return {}
    encoded_metadata = text[start:end].strip()
    if not encoded_metadata:
        return {}
    try:
        padding = "=" * ((4 - len(encoded_metadata) % 4) % 4)
        raw = base64.b64decode((encoded_metadata + padding).encode("ascii"))
        try:
            decoded = zlib.decompress(raw).decode("utf-8")
        except zlib.error:
            decoded = raw.decode("utf-8")
        value = json.loads(decoded)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def completed_status_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    if str(metadata.get("state", "") or "") == "completed":
        return metadata
    prior = metadata.get("previous_completed")
    return prior if isinstance(prior, dict) else {}


def visible_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    rendered: list[str] = []
    for char in text:
        if char == "\n":
            rendered.append("\\n")
        elif char == "\r":
            rendered.append("\\r")
        elif char == "\t":
            rendered.append("\\t")
        elif ord(char) < 32 or ord(char) == 127:
            rendered.append(f"\\x{ord(char):02x}")
        else:
            rendered.append(char)
    return "".join(rendered)


def safe_inline_text(value: Any) -> str:
    return f"<span>{html.escape(visible_text(value), quote=False)}</span>"


def safe_inline_code(value: Any) -> str:
    return f"<code>{html.escape(visible_text(value), quote=False)}</code>"
