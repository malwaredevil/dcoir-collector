from __future__ import annotations

import base64
import html
import json
import zlib
from typing import Any

from dcoir_review.status import STATUS_MARKER

STATUS_METADATA_PREFIX = "<!-- dcoir-review-status-meta:v1:"
STATUS_METADATA_SUFFIX = " -->"
SEVERITY_ORDER = ("critical", "high", "medium", "low")
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
    if not isinstance(finding, dict):
        return ""
    existing = str(finding.get("identity", "") or "").strip()
    if existing:
        return existing
    path = str(finding.get("path", "") or "").strip()
    title = str(finding.get("title", "") or "").strip().casefold()
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    if not path and not title:
        return ""
    return f"{path}:{line}:{title}"


def _encode_metadata_payload(metadata: dict[str, Any]) -> str:
    payload = json.dumps(
        metadata,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    return base64.b64encode(compressed).decode("ascii").rstrip("=")


def _compact_metadata_finding(item: Any) -> dict[str, Any]:
    finding = item if isinstance(item, dict) else {}
    return {
        "identity": str(finding.get("identity", "") or "")[:240],
        "title": str(finding.get("title", "") or "")[:120],
        "severity": normalize_severity(finding.get("severity")),
        "path": str(finding.get("path", "") or "")[:160],
        "line": int(finding.get("line", 0) or 0),
        "url": str(finding.get("url", "") or "")[:240],
        "carried": bool(finding.get("carried", False)),
    }


def encode_status_metadata(metadata: dict[str, Any]) -> str:
    bounded = dict(metadata)
    encoded_metadata = _encode_metadata_payload(bounded)
    if len(encoded_metadata) > MAX_STATUS_METADATA_ENCODED_CHARS:
        bounded["provenance_truncated"] = True
        bounded["open_findings"] = [
            _compact_metadata_finding(item)
            for item in bounded.get("open_findings", [])[:6]
        ]
        previous = bounded.get("previous_completed")
        if isinstance(previous, dict):
            bounded_previous = dict(previous)
            bounded_previous["open_findings"] = [
                _compact_metadata_finding(item)
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
        raw = base64.b64decode(
            (encoded_metadata + padding).encode("ascii")
        )
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


def _visible_text(value: Any) -> str:
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


def _safe_inline_text(value: Any) -> str:
    return f"<span>{html.escape(_visible_text(value), quote=False)}</span>"


def _safe_inline_code(value: Any) -> str:
    return f"<code>{html.escape(_visible_text(value), quote=False)}</code>"


def _render_finding(finding: dict[str, Any]) -> str:
    title = str(finding.get("title", "") or "DCOIR Review finding").strip()
    severity = normalize_severity(finding.get("severity")).upper()
    location = _finding_location(finding)
    url = str(finding.get("url", "") or "").strip()
    carried = " — carried from the prior review" if finding.get("carried") else ""
    label = (
        f"- **{severity}** {_safe_inline_text(title)}"
        f" — {_safe_inline_code(location)}{carried}"
    )
    return f"{label} ([open review comment]({url}))" if url else label


def _render_changed_file(item: dict[str, Any]) -> str:
    path = str(item.get("path", "") or "").strip()
    status = str(item.get("status", "") or "modified").strip()
    additions = item.get("additions", 0)
    deletions = item.get("deletions", 0)
    return (
        f"- {_safe_inline_code(path)}"
        f" — {_safe_inline_text(status)}, +{additions}/-{deletions}"
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
    if state != "completed" and previous:
        metadata["previous_completed"] = {
            key: previous.get(key)
            for key in metadata_keys
            if key in previous
        }
        metadata["previous_completed"]["open_findings"] = _finding_list(
            previous.get("open_findings")
        )[:24]
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
        finding_identity(item): item
        for item in findings
        if finding_identity(item)
    }
    prior_by_id = {
        finding_identity(item): item
        for item in prior_findings
        if finding_identity(item)
    }
    same_head = bool(
        previous
        and str(previous.get("reviewed_head_sha", "") or "").strip()
        and str(previous.get("reviewed_head_sha", "") or "").strip() == reviewed_head
    )
    resolved = []
    if previous and not same_head and gate_status != "indeterminate":
        resolved = [item for key, item in prior_by_id.items() if key not in current_by_id]
    previously_missed = []
    if same_head:
        previously_missed = [
            item for key, item in current_by_id.items() if key not in prior_by_id
        ]

    if findings:
        headline = "🟡 Changes recommended"
        plural = "s" if len(findings) != 1 else ""
        summary = f"{len(findings)} open verifier-supported finding{plural} require attention."
    elif gate_status == "indeterminate":
        headline = "🔵 Needs a closer look"
        summary = "The review completed, but prior verified-finding state could not be confirmed safely."
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

    if resolved:
        lines.extend(
            [
                "",
                "<details>",
                f"<summary><strong>Resolved since last review ({len(resolved)})</strong></summary>",
                "",
            ]
        )
        lines.extend(_render_finding(item) for item in resolved)
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
