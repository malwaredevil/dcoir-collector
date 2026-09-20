from __future__ import annotations

import base64
import hashlib
import html
import json
import string
import zlib
from typing import Any

STATUS_METADATA_PREFIX = "<!-- dcoir-review-status-meta:v1:"
STATUS_METADATA_SUFFIX = " -->"
MAX_STATUS_METADATA_ENCODED_CHARS = 6000
MINIMAL_METADATA_KEYS = (
    "schema",
    "state",
    "pr_number",
    "command",
    "context_mode",
    "model_outcome",
    "review_event",
    "reviewed_head_sha",
    "workflow_run_id",
    "workflow_run_url",
    "formal_review_id",
    "formal_review_url",
    "gate_status",
    "finding_count",
    "finding_identity_index_complete",
    "open_finding_identities",
    "finding_gate_identity_map_complete",
    "open_finding_gate_identities",
    "previous_completed",
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


def finding_identity_token(finding: Any) -> str:
    identity = canonical_finding_identity(finding)
    if not identity:
        return ""
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"finding-id:{digest[:24]}"


def finding_identity_index(findings: Any) -> list[str]:
    if not isinstance(findings, list):
        return []
    identities: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        identity = finding_identity_token(finding)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        identities.append(identity)
    return identities


def finding_gate_identity_map(findings: Any) -> dict[str, list[str]]:
    if not isinstance(findings, list):
        return {}
    identities: dict[str, list[str]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fingerprint = str(finding.get("gate_fingerprint", "") or "").strip().lower()
        identity = canonical_finding_identity(finding)
        if (
            len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
            or not identity
        ):
            continue
        values = identities.setdefault(fingerprint, [])
        if identity not in values:
            values.append(identity)
    return identities


def finding_gate_identity_map_complete(findings: Any) -> bool:
    if not isinstance(findings, list):
        return False
    mapping = finding_gate_identity_map(findings)
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        identity = canonical_finding_identity(finding)
        if not identity:
            continue
        fingerprint = str(finding.get("gate_fingerprint", "") or "").strip().lower()
        if identity not in mapping.get(fingerprint, []):
            return False
    return True


def metadata_gate_identity_state(metadata: Any) -> tuple[dict[str, list[str]], bool]:
    if not isinstance(metadata, dict):
        return {}, False
    raw_mapping = metadata.get("open_finding_gate_identities")
    if not isinstance(raw_mapping, dict):
        return {}, False
    mapping: dict[str, list[str]] = {}
    for raw_fingerprint, raw_identities in raw_mapping.items():
        fingerprint = str(raw_fingerprint or "").strip().lower()
        if (
            len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
            or not isinstance(raw_identities, list)
        ):
            continue
        identities = [
            identity
            for value in raw_identities
            if (identity := _existing_identity(value))
        ]
        if identities:
            mapping[fingerprint] = list(dict.fromkeys(identities))
    return mapping, bool(metadata.get("finding_gate_identity_map_complete", False))


def metadata_finding_identity_state(metadata: Any) -> tuple[list[str], bool]:
    if not isinstance(metadata, dict):
        return [], False
    raw_identities = metadata.get("open_finding_identities")
    if isinstance(raw_identities, list):
        identities = [
            str(value or "").strip()
            for value in raw_identities
            if str(value or "").strip()
        ]
        return identities, bool(metadata.get("finding_identity_index_complete", False))

    findings = metadata.get("open_findings")
    detail_findings = findings if isinstance(findings, list) else []
    identities = finding_identity_index(detail_findings)
    try:
        finding_count = int(metadata.get("finding_count", len(detail_findings)) or 0)
    except (TypeError, ValueError):
        finding_count = len(detail_findings)
    return identities, finding_count == len(detail_findings)


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
        "line": _finding_line(finding.get("line", 0)),
        "url": str(finding.get("url", "") or "")[:240],
        "url_kind": str(finding.get("url_kind", "") or "")[:32],
        "carried": bool(finding.get("carried", False)),
        "identity_unmatched": bool(finding.get("identity_unmatched", False)),
    }


def _compact_metadata_scalars(metadata: dict[str, Any]) -> None:
    limits = {
        "command": 512,
        "workflow_run_url": 240,
        "formal_review_url": 240,
        "workflow_run_id": 64,
        "model_outcome": 120,
        "context_mode": 64,
        "review_event": 64,
    }
    for key, limit in limits.items():
        value = metadata.get(key)
        if value is None:
            continue
        metadata[key] = str(value or "")[:limit]
    previous = metadata.get("previous_completed")
    if isinstance(previous, dict):
        bounded_previous = dict(previous)
        for key, limit in limits.items():
            value = bounded_previous.get(key)
            if value is None:
                continue
            bounded_previous[key] = str(value or "")[:limit]
        metadata["previous_completed"] = bounded_previous


def encode_status_metadata(metadata: dict[str, Any], normalize_severity: Any) -> str:
    bounded = dict(metadata)
    encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded["provenance_truncated"] = True
        _compact_metadata_scalars(bounded)
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
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
        bounded["finding_identity_index_complete"] = False
        bounded["open_finding_identities"] = []
        bounded["finding_gate_identity_map_complete"] = False
        bounded["open_finding_gate_identities"] = {}
        bounded["finding_identity_index_truncated"] = True
        encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        previous = bounded.get("previous_completed")
        if isinstance(previous, dict):
            bounded["previous_completed"] = {
                key: previous.get(key)
                for key in MINIMAL_METADATA_KEYS
                if key != "previous_completed" and key in previous
            }
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
        previous = bounded.get("previous_completed")
        bounded = {
            key: bounded.get(key)
            for key in MINIMAL_METADATA_KEYS
            if key in bounded
            and key not in ("open_finding_identities", "open_finding_gate_identities", "previous_completed")
        }
        if isinstance(previous, dict):
            bounded["previous_completed"] = {
                "reviewed_head_sha": str(previous.get("reviewed_head_sha", "") or "")[:64],
                "finding_identity_index_complete": False,
                "finding_gate_identity_map_complete": False,
            }
        bounded["metadata_truncated"] = True
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


def _html_markdown_literal(value: Any) -> str:
    text = visible_text(value)
    return "".join(
        f"&#{ord(char)};" if char in string.punctuation else html.escape(char, quote=False)
        for char in text
    )


def safe_inline_text(value: Any) -> str:
    return f"<span>{_html_markdown_literal(value)}</span>"


def safe_inline_code(value: Any) -> str:
    return f"<code>{_html_markdown_literal(value)}</code>"
