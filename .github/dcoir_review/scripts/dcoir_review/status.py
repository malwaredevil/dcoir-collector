from __future__ import annotations

import base64
import json
import sys
from typing import Any

STATUS_MARKER = "<!-- dcoir-review-status:v1 -->"
STATUS_METADATA_PREFIX = "<!-- dcoir-review-status-meta:v1:"
STATUS_METADATA_SUFFIX = " -->"
MAX_COMMENT_PAGES = 20
SEVERITY_ORDER = ("critical", "high", "medium", "low")


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
    path = str(finding.get("path", "") or "").strip()
    title = str(finding.get("title", "") or "").strip().casefold()
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    if not path and not title:
        return ""
    return f"{path}:{line}:{title}"


def encode_status_metadata(metadata: dict[str, Any]) -> str:
    payload = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{STATUS_METADATA_PREFIX}{token}{STATUS_METADATA_SUFFIX}"


def parse_status_metadata(body: str) -> dict[str, Any]:
    text = str(body or "")
    start = text.find(STATUS_METADATA_PREFIX)
    if start < 0:
        return {}
    start += len(STATUS_METADATA_PREFIX)
    end = text.find(STATUS_METADATA_SUFFIX, start)
    if end < 0:
        return {}
    token = text[start:end].strip()
    if not token:
        return {}
    try:
        padding = "=" * ((4 - len(token) % 4) % 4)
        decoded = base64.urlsafe_b64decode((token + padding).encode("ascii")).decode("utf-8")
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
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


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
    carried = " — carried from the prior review" if finding.get("carried") else ""
    label = f"**{severity}** {title} — `{location}`{carried}"
    return f"- [{label}]({url})" if url else f"- {label}"


def _render_changed_file(item: dict[str, Any]) -> str:
    path = str(item.get("path", "") or "").strip()
    status = str(item.get("status", "") or "modified").strip()
    additions = item.get("additions", 0)
    deletions = item.get("deletions", 0)
    return f"- `{path}` — {status}, +{additions}/-{deletions}"


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

    metadata = dict(snapshot)
    metadata["open_findings"] = findings
    if state != "completed" and previous:
        metadata["previous_completed"] = previous

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
    current_by_id = {finding_identity(item): item for item in findings if finding_identity(item)}
    prior_by_id = {finding_identity(item): item for item in prior_findings if finding_identity(item)}
    same_head = bool(
        previous
        and str(previous.get("reviewed_head_sha", "") or "").strip()
        and str(previous.get("reviewed_head_sha", "") or "").strip() == reviewed_head
    )
    resolved = []
    if previous and not same_head:
        resolved = [item for key, item in prior_by_id.items() if key not in current_by_id]
    previously_missed = []
    if same_head:
        previously_missed = [item for key, item in current_by_id.items() if key not in prior_by_id]

    if findings:
        headline = "🟡 Changes recommended"
        summary = f"{len(findings)} open verifier-supported finding{'s' if len(findings) != 1 else ''} require attention."
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
        lines.extend(["", "<details open>", f"<summary><strong>Open ({len(findings)})</strong></summary>", ""])
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

    changed_files = [dict(item) for item in snapshot.get("changed_files", []) if isinstance(item, dict)]
    if changed_files:
        lines.extend(["", "<details>", "<summary><strong>What changed in this PR</strong></summary>", ""])
        for item in changed_files[:12]:
            lines.append(_render_changed_file(item))
        if len(changed_files) > 12:
            lines.append(f"- ... and {len(changed_files) - 12} more changed file(s)")
        lines.extend(["", "</details>"])

    return _bounded("\n".join(lines).strip())


def _is_bot_authored(comment: Any) -> bool:
    if not isinstance(comment, dict):
        return False
    user = comment.get("user")
    if not isinstance(user, dict):
        return False
    login = str(user.get("login", "") or "").strip().lower()
    account_type = str(user.get("type", "") or "").strip().lower()
    return account_type == "bot" or login.endswith("[bot]")


class MutableReviewStatusComment:
    """Best-effort owner for the single mutable DCOIR Review status comment.

    Publication is deliberately observational: GitHub API failure is reported to
    stderr and returned as False, but never raised into review disposition.
    """

    def __init__(self, gh: Any, issue_number: int) -> None:
        self.gh = gh
        self.issue_number = int(issue_number)
        self.comment_id = 0
        self.last_body = ""
        self.last_discovered_body = ""
        self.last_error = ""
        self._body_by_id: dict[int, str] = {}

    def _canonical_comment_ids(self) -> list[int]:
        matches: list[int] = []
        self._body_by_id = {}
        try:
            repo = str(getattr(self.gh, "repo", "") or "").strip()
            if not repo:
                return []
            for page in range(1, MAX_COMMENT_PAGES + 1):
                batch = self.gh.request(
                    "GET",
                    f"/repos/{repo}/issues/{self.issue_number}/comments?per_page=100&page={page}",
                )
                if not isinstance(batch, list) or not batch:
                    break
                for comment in batch:
                    if not _is_bot_authored(comment):
                        continue
                    body = str(comment.get("body", "") or "")
                    if STATUS_MARKER not in body:
                        continue
                    try:
                        comment_id = int(comment.get("id", 0) or 0)
                    except (TypeError, ValueError):
                        comment_id = 0
                    if comment_id > 0:
                        matches.append(comment_id)
                        self._body_by_id[comment_id] = body
                if len(batch) < 100:
                    break
        except Exception as exc:
            self._warn(f"unable to discover canonical status comment: {exc}")
            return []
        return sorted(set(matches))

    def discover(self) -> int:
        """Reuse the earliest bot-authored canonical status comment on this PR."""
        matches = self._canonical_comment_ids()
        if not matches:
            return 0
        self.comment_id = matches[0]
        self.last_discovered_body = self._body_by_id.get(self.comment_id, "")
        return self.comment_id

    def _reconcile_created_comment(self) -> None:
        matches = self._canonical_comment_ids()
        if not matches:
            return
        canonical_id = matches[0]
        self.comment_id = canonical_id
        self.last_discovered_body = self._body_by_id.get(canonical_id, "")
        repo = str(getattr(self.gh, "repo", "") or "").strip()
        if not repo:
            return
        for duplicate_id in matches[1:]:
            try:
                self.gh.request("DELETE", f"/repos/{repo}/issues/comments/{duplicate_id}")
            except Exception as exc:
                self._warn(f"unable to delete duplicate canonical status comment {duplicate_id}: {exc}")

    def publish(self, body: str, *, create_if_missing: bool = True, force: bool = False) -> bool:
        """Create or update the canonical comment without affecting review outcome."""
        canonical = str(body or "")
        if STATUS_MARKER not in canonical:
            canonical = f"{STATUS_MARKER}\n{canonical}".rstrip()
        if not force and canonical == self.last_body:
            return True

        try:
            if not self.comment_id:
                self.discover()
            if self.comment_id:
                self.gh.update_issue_comment(self.comment_id, canonical)
            elif create_if_missing:
                comment = self.gh.create_issue_comment(self.issue_number, canonical)
                created_comment_id = int(comment.get("id", 0) or 0)
                self.comment_id = created_comment_id
                self._reconcile_created_comment()
                if self.comment_id and self.comment_id != created_comment_id:
                    self.gh.update_issue_comment(self.comment_id, canonical)
            else:
                return False
            self.last_body = canonical
            self.last_error = ""
            return True
        except Exception as exc:
            self._warn(f"unable to publish canonical status comment: {exc}")
            return False

    def _warn(self, message: str) -> None:
        self.last_error = str(message or "")[:1000]
        print(f"WARN: {self.last_error}", file=sys.stderr, flush=True)
