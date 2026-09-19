from __future__ import annotations

from typing import Any, Callable

from dcoir_review import semantic_candidate_identity as candidate_identity
from dcoir_review.status_overview import (
    completed_status_metadata,
    finding_identity,
    normalize_severity,
)


Sanitizer = Callable[[str], str]


def _stable_finding_identity(finding: dict[str, Any]) -> str:
    semantic_key = candidate_identity._raw_key(
        finding.get(candidate_identity.SEMANTIC_KEY_FIELD)
    )
    if semantic_key is not None:
        path, line, kind = semantic_key
        return f"semantic-key:{path}:{line}:{kind}"
    candidate_id = str(finding.get(candidate_identity.CANDIDATE_ID_FIELD, "") or "").strip()
    if candidate_id:
        return f"candidate-id:{candidate_id}"
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
        }
        item["identity"] = _stable_finding_identity(finding)
        normalized.append(item)
    return normalized


def attach_review_comment_urls(
    findings: list[dict[str, Any]],
    comments: Any,
    fallback_url: str,
) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in findings]
    if not isinstance(comments, list):
        return normalized
    unused = list(normalized)
    for comment in comments:
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
        match = next(
            (
                item
                for item in unused
                if str(item.get("path", "") or "") == path
                and int(item.get("line", 0) or 0) == line
            ),
            None,
        )
        if match is None:
            continue
        match["url"] = str(comment.get("html_url", "") or fallback_url).strip()
        unused.remove(match)
    for item in unused:
        if not item.get("url"):
            item["url"] = fallback_url
    return normalized


def prior_completed(metadata: Any) -> dict[str, Any]:
    return completed_status_metadata(metadata)


def merge_open_findings(
    findings: list[dict[str, Any]],
    gate_state: Any,
    previous_completed: dict[str, Any],
    formal_review_url: str,
) -> list[dict[str, Any]]:
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
    for record in state.get("unresolved_findings", []) or []:
        if not isinstance(record, dict) or record.get("status") != "carried-unresolved":
            continue
        path = str(record.get("path", "") or "")
        try:
            line = int(record.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        matched = False
        for prior_item in by_location.get((path, line), []):
            item = dict(prior_item)
            item["carried"] = True
            identity = _stable_finding_identity(item)
            if identity and identity in known:
                continue
            if identity:
                known.add(identity)
            current.append(item)
            matched = True
        if matched:
            continue
        item = {
            "title": "Prior verifier-supported finding remains unresolved",
            "severity": "medium",
            "path": path,
            "line": line,
            "url": formal_review_url,
            "carried": True,
        }
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
