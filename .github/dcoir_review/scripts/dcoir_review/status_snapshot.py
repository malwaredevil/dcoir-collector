from __future__ import annotations

from typing import Any, Callable

from dcoir_review.status_overview import (
    completed_status_metadata,
    finding_identity,
    normalize_severity,
)
from dcoir_review import status_overview_support as support
from dcoir_review import verified_finding_gate_state as gate_state


Sanitizer = Callable[[str], str]


def _stable_finding_identity(finding: dict[str, Any]) -> str:
    return finding_identity(finding)


def normalize_changed_files(files: Any, sanitize: Sanitizer) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(files, list):
        return normalized
    for item in files:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "path": sanitize(str(item.get("filename", "") or "")),
                "status": sanitize(str(item.get("status", "") or "modified")),
                "additions": int(item.get("additions", 0) or 0),
                "deletions": int(item.get("deletions", 0) or 0),
            }
        )
    return normalized


def _plain_text(value: str) -> str:
    return str(value or "")


def _review_anchors(finding: dict[str, Any], sanitize: Sanitizer) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    raw_anchors = finding.get("_dcoir_status_review_anchors")
    if not isinstance(raw_anchors, list):
        return anchors
    for anchor in raw_anchors[:6]:
        if not isinstance(anchor, dict):
            continue
        path = sanitize(str(anchor.get("path", "") or ""))[:500]
        try:
            line = int(anchor.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        if path and line > 0:
            anchors.append({"path": path, "line": line})
    return anchors


def normalize_findings(findings: Any, sanitize: Sanitizer) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(findings, list):
        return normalized
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        try:
            line = int(finding.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        item = {
            "title": sanitize(
                str(finding.get("title", "") or "DCOIR Review finding")
            )[:200],
            "severity": normalize_severity(finding.get("severity")),
            "path": sanitize(str(finding.get("path", "") or ""))[:500],
            "line": line,
            "url": "",
            "url_kind": "",
        }
        item["identity"] = _stable_finding_identity(finding)
        item["gate_fingerprint"] = gate_state.finding_fingerprint(finding)
        anchors = _review_anchors(finding, sanitize)
        if anchors:
            item["review_anchors"] = anchors
        normalized.append(item)
    return normalized


def attach_review_comment_urls(
    findings: list[dict[str, Any]],
    comments: Any,
    fallback_url: str,
) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in findings]
    review_comments = comments if isinstance(comments, list) else []
    unused = list(normalized)
    for comment in review_comments:
        if not isinstance(comment, dict):
            continue
        path = str(comment.get("path", "") or "").strip()
        try:
            line = int(
                comment.get("line", 0)
                or comment.get("original_line", 0)
                or 0
            )
        except (TypeError, ValueError):
            line = 0

        def matches(item: dict[str, Any]) -> bool:
            anchors = item.get("review_anchors")
            if isinstance(anchors, list):
                for anchor in anchors:
                    if not isinstance(anchor, dict):
                        continue
                    if (
                        str(anchor.get("path", "") or "") == path
                        and int(anchor.get("line", 0) or 0) == line
                    ):
                        return True
            return (
                str(item.get("path", "") or "") == path
                and int(item.get("line", 0) or 0) == line
            )

        match = next((item for item in unused if matches(item)), None)
        if match is None:
            continue
        comment_url = str(comment.get("html_url", "") or "").strip()
        if comment_url:
            match["url"] = comment_url
            match["url_kind"] = "review_comment"
        elif fallback_url:
            match["url"] = fallback_url
            match["url_kind"] = "formal_review"
        unused.remove(match)
    for item in normalized:
        if not item.get("url") and fallback_url:
            item["url"] = fallback_url
            item["url_kind"] = "formal_review"
        item.pop("review_anchors", None)
    return normalized

def prior_completed(metadata: Any) -> dict[str, Any]:
    return completed_status_metadata(metadata)


def merge_open_findings(
    findings: list[dict[str, Any]],
    gate_state: Any,
    previous_completed: dict[str, Any],
    formal_review_url: str,
    sanitize: Sanitizer | None = None,
) -> list[dict[str, Any]]:
    del formal_review_url
    sanitize_value = sanitize if callable(sanitize) else _plain_text
    current = [dict(item) for item in findings]
    known = {
        _stable_finding_identity(item)
        for item in current
        if _stable_finding_identity(item)
    }
    state = gate_state if isinstance(gate_state, dict) else {}
    if str(state.get("gate_status", "") or "") != "blocked":
        return current
    prior_findings = [
        dict(item)
        for item in previous_completed.get("open_findings", [])
        if isinstance(item, dict)
    ]
    by_location: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for item in prior_findings:
        key = (str(item.get("path", "") or ""), int(item.get("line", 0) or 0))
        by_location.setdefault(key, []).append(item)
    prior_review_url = str(previous_completed.get("formal_review_url", "") or "").strip()
    prior_gate_identities, prior_gate_identity_complete = support.metadata_gate_identity_state(
        previous_completed
    )

    for record in state.get("unresolved_findings", []) or []:
        if not isinstance(record, dict) or record.get("status") != "carried-unresolved":
            continue
        raw_path = str(record.get("path", "") or "")
        safe_path = sanitize_value(raw_path)[:500]
        try:
            line = int(record.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        fingerprint = str(record.get("fingerprint", "") or "").strip().lower()

        location_keys = [(raw_path, line)]
        if safe_path != raw_path:
            location_keys.append((safe_path, line))
        matched_items: list[dict[str, Any]] = []
        for key in location_keys:
            matched_items.extend(by_location.get(key, []))

        matched = False
        seen_prior_ids: set[str] = set()
        for prior_item in matched_items:
            item = dict(prior_item)
            item["gate_fingerprint"] = fingerprint
            identity = _stable_finding_identity(item)
            if identity and identity in seen_prior_ids:
                continue
            if identity:
                seen_prior_ids.add(identity)
            item["carried"] = True
            if identity and identity in known:
                continue
            if identity:
                known.add(identity)
            current.append(item)
            matched = True

        mapped_identities = (
            prior_gate_identities.get(fingerprint, [])
            if prior_gate_identity_complete
            else []
        )
        for mapped_identity in mapped_identities:
            if mapped_identity in seen_prior_ids or mapped_identity in known:
                continue
            item = {
                "title": "Prior verifier-supported finding remains unresolved",
                "severity": normalize_severity(record.get("severity") or "medium"),
                "path": safe_path,
                "line": line,
                "url": prior_review_url,
                "url_kind": "formal_review" if prior_review_url else "",
                "carried": True,
                "identity": mapped_identity,
                "gate_fingerprint": fingerprint,
            }
            known.add(mapped_identity)
            current.append(item)
            matched = True
        if matched:
            continue

        severity = normalize_severity(record.get("severity") or "medium")
        item = {
            "title": "Prior verifier-supported finding remains unresolved",
            "severity": severity,
            "path": safe_path,
            "line": line,
            "url": prior_review_url,
            "url_kind": "formal_review" if prior_review_url else "",
            "carried": True,
            "gate_fingerprint": fingerprint,
        }
        if len(fingerprint) == 64 and all(char in "0123456789abcdef" for char in fingerprint):
            item["identity"] = f"finding-digest:{fingerprint[:32]}"
        item["identity_unmatched"] = True
        identity = _stable_finding_identity(item)
        if identity and identity in known:
            continue
        if identity:
            known.add(identity)
        current.append(item)
    return current

def public_progress_for_stage(stage: str) -> str:
    value = str(stage or "").lower()
    if "github-review" in value or "publish" in value:
        return "Publishing the GitHub review"
    if any(
        token in value
        for token in ("normalize", "verif", "repair", "adjudication", "gate")
    ):
        return "Validating review findings"
    if any(
        token in value
        for token in ("provider", "prompt", "semantic", "risk", "per-file", "review-mode")
    ):
        return "Reviewing changed code"
    if any(
        token in value
        for token in ("github", "context", "assist", "reaction")
    ):
        return "Preparing review context"
    return "Review in progress"
