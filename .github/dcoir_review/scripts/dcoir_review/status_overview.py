from __future__ import annotations

from typing import Any

from dcoir_review.status import STATUS_MARKER
from dcoir_review import status_overview_support as support

SEVERITY_ORDER = ("critical", "high", "medium", "low")
MAX_STATUS_METADATA_ENCODED_CHARS = support.MAX_STATUS_METADATA_ENCODED_CHARS


def normalize_severity(value: Any) -> str:
    severity = str(value or "medium").strip().lower()
    if severity in {"p0", "critical"}:
        return "critical"
    if severity in {"p1", "high"}:
        return "high"
    if severity in {"p2", "medium", "moderate"}:
        return "medium"
    if severity in {"p3", "low"}:
        return "low"
    return "medium"


def finding_identity(finding: Any) -> str:
    return support.canonical_finding_identity(finding)


def encode_status_metadata(metadata: dict[str, Any]) -> str:
    return support.encode_status_metadata(metadata, normalize_severity)


def parse_status_metadata(body: str) -> dict[str, Any]:
    return support.parse_status_metadata(body)


def completed_status_metadata(metadata: Any) -> dict[str, Any]:
    return support.completed_status_metadata(metadata)


def _finding_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[normalize_severity(finding.get("severity"))] += 1
    return counts


def _finding_location(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "").strip()
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    if path and line > 0:
        return f"{path}:{line}"
    return path or "review conversation"


def _render_finding(finding: dict[str, Any]) -> str:
    title = str(finding.get("title", "") or "DCOIR Review finding").strip()
    severity = normalize_severity(finding.get("severity")).upper()
    location = _finding_location(finding)
    url = str(finding.get("url", "") or "").strip()
    url_kind = str(finding.get("url_kind", "") or "").strip()
    if not url_kind and url:
        url_kind = "review_comment" if "#discussion_r" in url else "formal_review"
    carried = " — carried from the prior review" if finding.get("carried") else ""
    label = (
        f"- **{severity}** {support.safe_inline_text(title)}"
        f" — {support.safe_inline_code(location)}{carried}"
    )
    if not url:
        return label
    link_label = "open review comment" if url_kind == "review_comment" else "open formal review"
    return f"{label} ([{link_label}]({url}))"


def _render_changed_file(item: dict[str, Any]) -> str:
    path = str(item.get("path", "") or "").strip()
    status = str(item.get("status", "") or "modified").strip()
    additions = item.get("additions", 0)
    deletions = item.get("deletions", 0)
    return (
        f"- {support.safe_inline_code(path)}"
        f" — {support.safe_inline_text(status)}, +{additions}/-{deletions}"
    )


def _review_effort(snapshot: dict[str, Any]) -> str:
    context_mode = str(snapshot.get("context_mode", "") or "").strip().lower()
    if context_mode.startswith("deep"):
        return "Deep"
    count = len(snapshot.get("changed_files", []) or [])
    if count <= 4:
        return "Lite"
    if count <= 15:
        return "Balanced"
    return "Deep"


def _severity_summary(findings: list[dict[str, Any]]) -> str:
    counts = _severity_counts(findings)
    parts = [f"{counts[name]} {name}" for name in SEVERITY_ORDER if counts[name]]
    return ", ".join(parts) if parts else "0"


def _bounded(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 120] + "\n\n[truncated by DCOIR Review]"


def render_status_overview(
    snapshot: dict[str, Any],
    previous_completed: dict[str, Any] | None = None,
) -> str:
    state = str(snapshot.get("state", "") or "").strip().lower()
    previous = previous_completed if isinstance(previous_completed, dict) else {}
    findings = _finding_list(snapshot.get("open_findings"))
    reviewed_head = str(snapshot.get("reviewed_head_sha", "") or "pending").strip()
    command = str(snapshot.get("command", "") or "/dcoir-review").strip()
    progress = str(snapshot.get("progress", "") or "Review in progress").strip()
    run_id = str(snapshot.get("workflow_run_id", "") or "").strip()
    run_url = str(snapshot.get("workflow_run_url", "") or "").strip()
    review_url = str(snapshot.get("formal_review_url", "") or "").strip()
    gate_status = str(snapshot.get("gate_status", "") or "").strip().lower()

    metadata_keys = (
        "schema",
        "state",
        "pr_number",
        "command",
        "workflow_run_id",
        "workflow_run_url",
        "reviewed_head_sha",
        "context_mode",
        "model_outcome",
        "review_event",
        "formal_review_id",
        "formal_review_url",
        "gate_status",
        "finding_count",
    )
    metadata = {key: snapshot.get(key) for key in metadata_keys}
    metadata["open_findings"] = findings[:12]
    metadata["open_finding_identities"] = support.finding_identity_index(findings)
    metadata["finding_identity_index_complete"] = True
    metadata["open_finding_gate_identities"] = support.finding_gate_identity_map(findings)
    metadata["finding_gate_identity_map_complete"] = (
        support.finding_gate_identity_map_complete(findings)
    )
    if state != "completed" and previous:
        prior_identities, prior_identity_complete = support.metadata_finding_identity_state(
            previous
        )
        metadata["previous_completed"] = {
            key: previous.get(key)
            for key in metadata_keys
            if key in previous
        }
        metadata["previous_completed"]["open_findings"] = _finding_list(
            previous.get("open_findings")
        )[:24]
        metadata["previous_completed"]["open_finding_identities"] = prior_identities
        metadata["previous_completed"]["finding_identity_index_complete"] = (
            prior_identity_complete
        )
        prior_gate_identities, prior_gate_identity_complete = (
            support.metadata_gate_identity_state(previous)
        )
        metadata["previous_completed"]["open_finding_gate_identities"] = (
            prior_gate_identities
        )
        metadata["previous_completed"]["finding_gate_identity_map_complete"] = (
            prior_gate_identity_complete
        )
    lines = [STATUS_MARKER, encode_status_metadata(metadata), ""]

    if state in {"queued", "running"}:
        label = "Queued" if state == "queued" else "Running"
        icon = "⏳" if state == "queued" else "🔵"
        lines.extend(
            [
                "## DCOIR Review",
                "",
                f"### {icon} Review {label.lower()}",
                "",
                f"**Status:** {label}  ",
                f"**Reviewed commit:** `{reviewed_head}`  ",
                f"**Trigger:** `{command}`  ",
                f"**Progress:** {progress}",
            ]
        )
        if run_url:
            lines.append(f"**Workflow:** [run {run_id or 'details'}]({run_url})")
        return _bounded("\n".join(lines).strip())

    if state in {"failed", "stopped", "superseded"}:
        headline = {
            "failed": "🔴 Review failed",
            "stopped": "🔴 Review stopped",
            "superseded": "⚪ Review superseded",
        }.get(state, "🔴 Review failed")
        summary = {
            "failed": "The review did not complete successfully. Use the workflow run for detailed diagnostics.",
            "stopped": "The review stopped because its current-head safety condition could not be maintained.",
            "superseded": "The review was superseded because the pull request changed during execution.",
        }.get(state, "The review did not complete successfully.")
        lines.extend(
            [
                "## DCOIR Review overview",
                "",
                f"### {headline}",
                "",
                summary,
                "",
                f"**Reviewed commit:** `{reviewed_head}`  ",
                f"**Trigger:** `{command}`",
            ]
        )
        if run_url:
            lines.extend(["", f"[Open workflow run {run_id or 'details'}]({run_url})"])
        return _bounded("\n".join(lines).strip())

    prior_findings = _finding_list(previous.get("open_findings"))
    current_by_id = {
        support.finding_identity_token(item): item
        for item in findings
        if support.finding_identity_token(item)
    }
    prior_identities, prior_identity_complete = support.metadata_finding_identity_state(
        previous
    )
    prior_identity_set = set(prior_identities)
    prior_detail_by_id = {
        support.finding_identity_token(item): item
        for item in prior_findings
        if support.finding_identity_token(item)
    }
    identity_unmatched_present = any(item.get("identity_unmatched") for item in findings) or any(
        item.get("identity_unmatched") for item in prior_findings
    )
    same_head = bool(
        previous
        and str(previous.get("reviewed_head_sha", "") or "").strip()
        and str(previous.get("reviewed_head_sha", "") or "").strip() == reviewed_head
    )
    resolved_ids: list[str] = []
    if (
        previous
        and not same_head
        and gate_status != "indeterminate"
        and prior_identity_complete
        and not identity_unmatched_present
    ):
        resolved_ids = [
            identity
            for identity in prior_identities
            if identity not in current_by_id
        ]
    resolved = [
        prior_detail_by_id[identity]
        for identity in resolved_ids
        if identity in prior_detail_by_id
    ]
    resolved_detail_omitted = max(0, len(resolved_ids) - len(resolved))
    previously_missed = []
    if same_head and prior_identity_complete:
        previously_missed = [
            item for key, item in current_by_id.items() if key not in prior_identity_set
        ]

    if gate_status == "indeterminate":
        headline = "🔵 Needs a closer look"
        if findings:
            plural = "s" if len(findings) != 1 else ""
            summary = (
                f"{len(findings)} open verifier-supported finding{plural} require attention, "
                "but prior verified-finding state could not be confirmed safely."
            )
        else:
            summary = (
                "The review completed, but prior verified-finding state could not be confirmed safely."
            )
    elif findings:
        headline = "🟡 Changes recommended"
        plural = "s" if len(findings) != 1 else ""
        summary = f"{len(findings)} open verifier-supported finding{plural} require attention."
    else:
        headline = "🟢 Clean"
        summary = "No verifier-supported findings were published for this pull request."

    lines.extend(
        [
            "## DCOIR Review overview",
            "",
            f"### {headline}",
            "",
            summary,
            "",
            f"**Review effort:** {_review_effort(snapshot)}  ",
            f"**Findings:** {_severity_summary(findings)}  ",
            f"**Reviewed commit:** `{reviewed_head}`  ",
            f"**Trigger:** `{command}`",
        ]
    )
    if review_url:
        lines.append(f"**Formal review:** [open review]({review_url})")

    if findings:
        lines.extend(
            [
                "",
                "<details open>",
                f"<summary><strong>Open ({len(findings)})</strong></summary>",
                "",
            ]
        )
        for item in sorted(
            findings,
            key=lambda finding: (
                SEVERITY_ORDER.index(normalize_severity(finding.get("severity"))),
                _finding_location(finding),
            ),
        ):
            lines.append(_render_finding(item))
        lines.extend(["", "</details>"])

    resolved_count = len(resolved) + resolved_detail_omitted
    if resolved_count:
        lines.extend(
            [
                "",
                "<details>",
                f"<summary><strong>Resolved since last review ({resolved_count})</strong></summary>",
                "",
            ]
        )
        lines.extend(_render_finding(item) for item in resolved)
        if resolved_detail_omitted:
            noun = "finding" if resolved_detail_omitted == 1 else "findings"
            lines.append(
                f"- {resolved_detail_omitted} additional resolved {noun}; "
                "details were omitted from bounded prior-run provenance."
            )
        lines.extend(["", "</details>"])

    if previously_missed:
        lines.extend(
            [
                "",
                "<details>",
                f"<summary><strong>Previously missed ({len(previously_missed)})</strong></summary>",
                "",
                "These findings were newly reported by a rerun of the same reviewed commit.",
                "",
            ]
        )
        lines.extend(_render_finding(item) for item in previously_missed)
        lines.extend(["", "</details>"])

    changed_files = [
        dict(item)
        for item in snapshot.get("changed_files", [])
        if isinstance(item, dict)
    ]
    if changed_files:
        lines.extend(
            [
                "",
                "<details>",
                "<summary><strong>What changed in this PR</strong></summary>",
                "",
            ]
        )
        for item in changed_files[:12]:
            lines.append(_render_changed_file(item))
        if len(changed_files) > 12:
            lines.append(f"- ... and {len(changed_files) - 12} more changed file(s)")
        lines.extend(["", "</details>"])

    return _bounded("\n".join(lines).strip())
