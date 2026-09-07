"""Pure verified-finding gate-state rules for Architecture-B v50."""

from __future__ import annotations

import hashlib
from typing import Any

VERSION = "v50"
STATE_CONTRACT = "architecture-b-verified-finding-gate-v1"
DISPOSITION_CONTRACT = "architecture-b-verified-finding-gate-disposition-v1"
STATE_ARTIFACT_PATH = "metadata/verified-finding-gate-state-v50.json"
FINAL_ARTIFACT_PATH = "metadata/final-gate-disposition-v50.json"


def _clean_path(value: Any) -> str:
    return str(value or "").strip()


def _line_number(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finding_fingerprint(path: str, line: int, title: str) -> str:
    return _sha(f"{path}\0{line}\0{title.strip()}")


def current_finding_record(finding: dict[str, Any], reviewed_head: str) -> dict[str, Any]:
    path = _clean_path(finding.get("path"))
    line = _line_number(finding.get("line"))
    title = str(finding.get("title", "") or "").strip()
    return {
        "fingerprint": _finding_fingerprint(path, line, title),
        "path": path,
        "line": line,
        "severity": str(finding.get("severity", "") or "").strip().lower(),
        "origin_reviewed_head": reviewed_head,
        "last_confirmed_head": reviewed_head,
        "status": "current-unresolved",
        "source": "current-exact-head-publication",
    }


def legacy_comment_record(comment: dict[str, Any], prior_head: str) -> dict[str, Any]:
    path = _clean_path(comment.get("path"))
    line = _line_number(comment.get("line") or comment.get("original_line"))
    body = str(comment.get("body", "") or "")
    first_line = next((item.strip() for item in body.splitlines() if item.strip()), "")
    return {
        "fingerprint": _finding_fingerprint(path, line, first_line),
        "path": path,
        "line": line,
        "severity": "",
        "origin_reviewed_head": prior_head,
        "last_confirmed_head": prior_head,
        "status": "prior-unresolved",
        "source": "legacy-v45-github-inline-comment",
    }


def changed_paths(scope: Any) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    changed: set[str] = set()
    files = scope.get("files", [])
    if not isinstance(files, list):
        return changed
    for item in files:
        if not isinstance(item, dict):
            continue
        for field in ("filename", "previous_filename"):
            path = _clean_path(item.get(field))
            if path:
                changed.add(path)
    return changed


def incremental_scope(scope: Any) -> bool:
    return bool(
        isinstance(scope, dict)
        and str(scope.get("source", "") or "") == "incremental-reviewed-head"
        and not str(scope.get("fallback_reason", "") or "").strip()
        and str(scope.get("compare_status", "") or "").strip().lower() == "ahead"
        and _clean_path(scope.get("prior_reviewed_head_sha"))
        and _clean_path(scope.get("current_head_sha"))
    )


def _valid_fingerprint(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def validate_state(state: dict[str, Any], prior_head: str, run_id: str) -> str:
    checks = (
        (state.get("contract") == STATE_CONTRACT, "state-contract-mismatch"),
        (state.get("runtime_version") == VERSION, "state-runtime-mismatch"),
        (state.get("outcome") == "complete", "state-incomplete"),
        (_clean_path(state.get("reviewed_head")).lower() == prior_head.lower(), "state-head-mismatch"),
        (str(state.get("workflow_run_id", "") or "").strip() == run_id, "state-run-mismatch"),
        (str(state.get("gate_status", "") or "") in {"clear", "blocked", "indeterminate"}, "state-status-invalid"),
        (isinstance(state.get("unresolved_findings"), list), "state-findings-invalid"),
    )
    for passed, reason in checks:
        if not passed:
            return reason
    records = state["unresolved_findings"]
    for record in records:
        if not isinstance(record, dict):
            return "state-finding-invalid"
        if not _clean_path(record.get("path")) or not _valid_fingerprint(record.get("fingerprint")):
            return "state-finding-identity-invalid"
    status = str(state.get("gate_status", "") or "")
    if status == "clear" and records:
        return "state-clear-with-findings"
    if status == "blocked" and not records:
        return "state-blocked-without-findings"
    return ""


def carry_records(records: list[dict[str, Any]], changed: set[str], current_head: str) -> list[dict[str, Any]]:
    carried: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        path = _clean_path(record.get("path"))
        fingerprint = str(record.get("fingerprint", "") or "").lower()
        if not path or path in changed or not _valid_fingerprint(fingerprint) or fingerprint in seen:
            continue
        next_record = dict(record)
        next_record["fingerprint"] = fingerprint
        next_record["status"] = "carried-unresolved"
        next_record["carried_forward_head"] = current_head
        carried.append(next_record)
        seen.add(fingerprint)
    return carried


def _indeterminate(reason: str, prior_count: int = 0) -> dict[str, Any]:
    return {
        "status": "indeterminate",
        "carried_records": [],
        "reason": reason,
        "source": "trusted-prior-review",
        "indeterminate_prior_count": max(0, int(prior_count or 0)),
    }


def migrate_legacy_v45(
    disposition: dict[str, Any],
    comments: list[dict[str, Any]],
    prior_head: str,
    changed: set[str],
    current_head: str,
) -> dict[str, Any]:
    if _clean_path(disposition.get("reviewed_head_sha")).lower() != prior_head.lower():
        return _indeterminate("legacy-v45-head-mismatch")
    try:
        published = max(0, int(disposition.get("published_finding_count", 0) or 0))
    except (TypeError, ValueError):
        return _indeterminate("legacy-v45-published-count-invalid")
    if published == 0:
        return {
            "status": "clear",
            "carried_records": [],
            "reason": "legacy-v45-clean-migration",
            "source": "legacy-v45-disposition",
            "indeterminate_prior_count": 0,
        }
    usable = [item for item in comments if isinstance(item, dict)]
    if len(usable) != published:
        return _indeterminate("legacy-v45-inline-count-mismatch", published)
    records = [legacy_comment_record(item, prior_head) for item in usable]
    if any(not item["path"] or not item["line"] for item in records):
        return _indeterminate("legacy-v45-inline-anchor-invalid", published)
    carried = carry_records(records, changed, current_head)
    return {
        "status": "blocked" if carried else "clear",
        "carried_records": carried,
        "reason": "legacy-v45-inline-migration",
        "source": "legacy-v45-github-review-comments",
        "indeterminate_prior_count": 0,
    }


def compose_state(
    current_findings: list[dict[str, Any]],
    prior: dict[str, Any],
    reviewed_head: str,
    workflow_run_id: str,
) -> dict[str, Any]:
    current = [current_finding_record(item, reviewed_head) for item in current_findings if isinstance(item, dict)]
    carried = [dict(item) for item in prior.get("carried_records", []) if isinstance(item, dict)]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in carried + current:
        fingerprint = str(item.get("fingerprint", "") or "").lower()
        if not _valid_fingerprint(fingerprint) or fingerprint in seen:
            continue
        records.append(item)
        seen.add(fingerprint)
    indeterminate = str(prior.get("status", "") or "") == "indeterminate"
    gate_status = "indeterminate" if indeterminate else ("blocked" if records else "clear")
    return {
        "contract": STATE_CONTRACT,
        "runtime_version": VERSION,
        "outcome": "complete",
        "reviewed_head": reviewed_head,
        "workflow_run_id": workflow_run_id,
        "gate_status": gate_status,
        "current_published_count": len(current),
        "carried_unresolved_count": len(carried),
        "indeterminate_prior_count": int(prior.get("indeterminate_prior_count", 0) or 0),
        "prior_state_source": str(prior.get("source", "") or ""),
        "prior_state_reason": str(prior.get("reason", "") or ""),
        "unresolved_findings": records,
    }


def final_disposition(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": DISPOSITION_CONTRACT,
        "runtime_version": VERSION,
        "reviewed_head": state.get("reviewed_head", ""),
        "gate_status": state.get("gate_status", "indeterminate"),
        "current_published_count": int(state.get("current_published_count", 0) or 0),
        "carried_unresolved_count": int(state.get("carried_unresolved_count", 0) or 0),
        "unresolved_finding_count": len([item for item in state.get("unresolved_findings", []) if isinstance(item, dict)]),
        "indeterminate_prior_count": int(state.get("indeterminate_prior_count", 0) or 0),
        "prior_state_source": str(state.get("prior_state_source", "") or ""),
        "prior_state_reason": str(state.get("prior_state_reason", "") or ""),
    }
