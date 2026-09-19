from dcoir_review.status import MutableReviewStatusComment, STATUS_MARKER
from dcoir_review import status_overview as status_overview_helpers
from dcoir_review import status_snapshot as status_snapshot_helpers

class ProgressReporter:
    def __init__(self, gh: GitHubClient, issue_number: int, command: str, config: Config) -> None:
        self.gh = gh
        self.issue_number = issue_number
        self.command = command
        self.config = config
        self.comment_id = 0
        self.steps: list[tuple[str, str]] = []
        self.reviewed_commit = ""
        self.formal_review_id = 0
        self.formal_review_url = ""
        self.context_mode = ""
        self.changed_files: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.gate_state: dict[str, Any] = {}
        self.model_used = ""
        self.review_event = ""
        self.public_progress = "Waiting to start"
        self.started_at = time.time()
        self.completed_at = 0.0
        self._last_published_stage = ""
        self._status_comment = MutableReviewStatusComment(gh, issue_number)
        self._previous_status_metadata: dict[str, Any] = {}

    def _sanitize(self, value: str) -> str:
        return sanitize_github_output(str(value or ""), self.config)

    def start(self) -> None:
        discovered = self._status_comment.discover()
        if discovered:
            self.comment_id = discovered
            self._previous_status_metadata = status_overview_helpers.parse_status_metadata(
                self._status_comment.last_discovered_body
            )
        self.public_progress = "Queued for review"
        self._record("queued", "accepted operator review command and queued review execution")
        self._last_published_stage = "queued"
        self._update_comment(self._body("queued"), create_if_missing=True, force=True)

    def set_reviewed_commit(self, reviewed_commit: str) -> None:
        captured = str(reviewed_commit or "").strip()
        if captured == self.reviewed_commit:
            return
        self.reviewed_commit = captured
        if self.comment_id or self._status_comment.comment_id:
            self._update_comment(self._body("running"), create_if_missing=True, force=True)

    def set_context_mode(self, context_mode: str) -> None:
        self.context_mode = self._sanitize(str(context_mode or "").strip())

    def set_changed_files(self, files: Any) -> None:
        self.changed_files = status_snapshot_helpers.normalize_changed_files(files, self._sanitize)

    def set_findings(self, findings: Any) -> None:
        self.findings = status_snapshot_helpers.normalize_findings(findings, self._sanitize)

    def set_gate_state(self, state: Any) -> None:
        self.gate_state = dict(state) if isinstance(state, dict) else {}

    def set_formal_review(self, review: Any) -> None:
        if not isinstance(review, dict):
            return
        try:
            self.formal_review_id = int(review.get("id", 0) or 0)
        except (TypeError, ValueError):
            self.formal_review_id = 0
        self.formal_review_url = str(review.get("html_url", "") or "").strip()
        repo = str(getattr(self.gh, "repo", "") or "").strip()
        if not self.formal_review_url and self.formal_review_id and repo:
            self.formal_review_url = (
                f"https://github.com/{repo}/pull/{self.issue_number}"
                f"#pullrequestreview-{self.formal_review_id}"
            )
        if not self.formal_review_id or not repo or not self.findings:
            return
        try:
            comments = self.gh.request(
                "GET",
                f"/repos/{repo}/pulls/{self.issue_number}/reviews/"
                f"{self.formal_review_id}/comments?per_page=100",
            )
            self.findings = status_snapshot_helpers.attach_review_comment_urls(
                self.findings,
                comments,
                self.formal_review_url,
            )
        except Exception as exc:
            print(
                f"WARN: unable to read back formal review comments for status overview: {exc}",
                file=sys.stderr,
                flush=True,
            )

    def update(self, stage: str, message: str) -> None:
        self._record(stage, message)
        normalized_stage = sanitize_public_identity(str(stage or "").strip())
        self.public_progress = status_snapshot_helpers.public_progress_for_stage(normalized_stage)
        if normalized_stage == self._last_published_stage:
            return
        self._last_published_stage = normalized_stage
        self._update_comment(self._body("running"))

    def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
        self.model_used = self._sanitize(str(model_used or ""))
        self.review_event = self._sanitize(str(review_event or ""))
        plural = "finding" if findings_count == 1 else "findings"
        self.completed_at = time.time()
        self.public_progress = "Review completed"
        self._record(
            "completed",
            f"posted GitHub review; {findings_count} inline {plural}; event={review_event}",
        )
        self._last_published_stage = "completed"
        self._update_comment(
            self._body(
                "completed",
                final_lines=[
                    f"- Result: GitHub review posted with `{findings_count}` inline {plural}.",
                    f"- Review event: `{review_event}`.",
                ],
            ),
            create_if_missing=True,
            force=True,
        )

    def fail(self, message: str) -> None:
        safe_message = self._sanitize(message)
        self.completed_at = time.time()
        self.public_progress = "Review failed"
        self._record("failed", safe_message[:500])
        self._last_published_stage = "failed"
        self._update_comment(
            self._body(
                "failed",
                final_lines=[
                    "- Result: review failed before a usable PR review could be posted.",
                    "",
                    "```text",
                    safe_message[:4000],
                    "```",
                ],
            ),
            create_if_missing=True,
            force=True,
        )

    def _record(self, stage: str, message: str) -> None:
        safe_message = self._sanitize(message)
        self.steps.append((stage, safe_message))
        emit_status(stage, safe_message)

    def _status_snapshot_helpers.prior_completed(self) -> dict[str, Any]:
        return status_snapshot_helpers.prior_completed(self._previous_status_metadata)

    def _open_findings(self) -> list[dict[str, Any]]:
        return status_snapshot_helpers.merge_open_findings(
            self.findings,
            self.gate_state,
            self._status_snapshot_helpers.prior_completed(),
            self.formal_review_url,
        )

    def _snapshot(self, state: str) -> dict[str, Any]:
        return {
            "schema": "dcoir_review_status_overview_v1",
            "state": str(state or "").strip().lower(),
            "pr_number": int(self.issue_number),
            "command": self._sanitize(self.command),
            "workflow_run_id": self._sanitize(workflow_run_id()),
            "workflow_run_url": self._sanitize(workflow_run_url()),
            "reviewed_head_sha": self._sanitize(self.reviewed_commit or "pending"),
            "context_mode": self.context_mode,
            "model_outcome": self.model_used,
            "review_event": self.review_event,
            "formal_review_id": int(self.formal_review_id or 0),
            "formal_review_url": self._sanitize(self.formal_review_url),
            "gate_status": self._sanitize(
                str(self.gate_state.get("gate_status", "") or "")
            ),
            "finding_count": len(self._open_findings()),
            "open_findings": self._open_findings(),
            "changed_files": [dict(item) for item in self.changed_files],
            "progress": self._sanitize(self.public_progress),
        }

    def _body(self, state: str, final_lines: list[str] | None = None) -> str:
        if bool(getattr(self.config, "debug", False)):
            return self._debug_body(state, final_lines=final_lines)
        return status_overview_helpers.render_status_overview(self._snapshot(state), self._status_snapshot_helpers.prior_completed())

    def _debug_body(self, state: str, final_lines: list[str] | None = None) -> str:
        normalized = str(state or "").strip().lower()
        state_label = {
            "queued": "Queued",
            "running": "Running",
            "completed": "Completed",
            "failed": "Failed",
            "superseded": "Superseded",
            "stopped": "Stopped",
        }.get(normalized, "Failed")
        now = self.completed_at or time.time()
        elapsed = max(0, int(now - self.started_at))
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started_at))
        commit = self._sanitize(self.reviewed_commit or "pending")
        command = self._sanitize(self.command)
        lines = [
            STATUS_MARKER,
            status_overview_helpers.encode_status_metadata(self._snapshot(state)),
            f"## {REVIEW_DISPLAY_NAME} — {state_label}",
            "",
            f"- Exact reviewed commit: `{commit}`.",
            f"- Trigger: `{command}`.",
            f"- Started: `{started}`.",
            f"- Elapsed: `{elapsed}s`.",
            *workflow_run_status_lines(self.config),
        ]
        if self.formal_review_url:
            safe_url = self._sanitize(self.formal_review_url)
            review_label = str(self.formal_review_id or "review")
            lines.append(
                f"- Formal GitHub review: [`{review_label}`]({safe_url}) "
                "— authoritative review artifact."
            )
        else:
            lines.append(
                "- Formal GitHub review: pending; the status comment is progress-only."
            )
        if self.model_used:
            lines.append(f"- Provider/model outcome: `{self.model_used}`.")
        if self.context_mode:
            lines.append(f"- Context mode: `{self.context_mode}`.")
        if final_lines:
            lines.extend(["", *final_lines])
        if self.steps:
            lines.extend(
                [
                    "",
                    "<details open>",
                    "<summary>Detailed progress and diagnostics</summary>",
                    "",
                ]
            )
            for stage, message in self.steps:
                lines.append(f"- `{sanitize_public_identity(stage)}`: {message}")
            lines.extend(["", "</details>"])
        return github_safe_body("\n".join(lines), limit=12000)

    def _update_comment(
        self,
        body: str,
        create_if_missing: bool = True,
        force: bool = False,
    ) -> None:
        self._status_comment.comment_id = int(
            self.comment_id or self._status_comment.comment_id or 0
        )
        self._status_comment.publish(
            body,
            create_if_missing=create_if_missing,
            force=force,
        )
        self.comment_id = int(self._status_comment.comment_id or 0)


def build_diff_line_index(diff: str) -> dict[tuple[str, int], int]:
    mapping: dict[tuple[str, int], int] = {}
    current_path: str | None = None
    position = 0
    right_line: int | None = None
    seen_hunk = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            position = 0
            right_line = None
            seen_hunk = False
            continue
        if line.startswith("+++ b/"):
            current_path = line[6:]
            continue
        if line.startswith("@@"):
            # GitHub's review-comment `position` is 1-based from the first line
            # *after* the first hunk header. Subsequent hunk headers consume a
            # position as the patch continues, but the first hunk header does
            # not. Counting it shifted every first-hunk comment one line early.
            if seen_hunk:
                position += 1
            else:
                seen_hunk = True
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            right_line = int(match.group(1)) if match else None
            continue
        if current_path is None or right_line is None:
            continue
        position += 1
        if line.startswith("-") and not line.startswith("---"):
            continue
        mapping[(current_path, right_line)] = position
        right_line += 1
    return mapping


def extract_relevant_file_patches(diff: str, max_files: int) -> str:
    chunks = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    selected = [chunk for chunk in chunks if chunk.strip()]
    return "\n".join(selected[:max_files])


def load_guidance(config: Config) -> str:
    parts = []
    for path in config.guidance_files:
        text = read_text(path)
        if text:
            parts.append(f"## {path}\n\n{text}")
    return "\n\n".join(parts)
