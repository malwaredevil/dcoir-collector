from dcoir_review.status import MutableReviewStatusComment, STATUS_MARKER


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
        self.started_at = time.time()
        self.completed_at = 0.0
        self._last_published_stage = ""
        self._status_comment = MutableReviewStatusComment(gh, issue_number)

    def start(self) -> None:
        self._record("queued", "accepted operator review command and queued review execution")
        self._last_published_stage = "queued"
        self._update_comment(self._body("queued"), create_if_missing=True, force=True)

    def set_reviewed_commit(self, reviewed_commit: str) -> None:
        self.reviewed_commit = str(reviewed_commit or "").strip()

    def set_formal_review(self, review: Any) -> None:
        if not isinstance(review, dict):
            return
        try:
            self.formal_review_id = int(review.get("id", 0) or 0)
        except (TypeError, ValueError):
            self.formal_review_id = 0
        self.formal_review_url = str(review.get("html_url", "") or "").strip()
        if not self.formal_review_url and self.formal_review_id:
            repo = str(getattr(self.gh, "repo", "") or "").strip()
            if repo:
                self.formal_review_url = (
                    f"https://github.com/{repo}/pull/{self.issue_number}"
                    f"#pullrequestreview-{self.formal_review_id}"
                )

    def update(self, stage: str, message: str) -> None:
        self._record(stage, message)
        normalized_stage = sanitize_public_identity(str(stage or "").strip())
        if normalized_stage == self._last_published_stage:
            return
        self._last_published_stage = normalized_stage
        self._update_comment(self._body("running"))

    def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
        plural = "finding" if findings_count == 1 else "findings"
        self.completed_at = time.time()
        self._record("completed", f"posted GitHub review; {findings_count} inline {plural}; event={review_event}")
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
        safe_message = sanitize_github_output(message, self.config)
        self.completed_at = time.time()
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
        safe_message = sanitize_github_output(message, self.config)
        self.steps.append((stage, safe_message))
        emit_status(stage, safe_message)

    def _body(self, state: str, final_lines: list[str] | None = None) -> str:
        normalized = str(state or "").strip().lower()
        state_label = {
            "queued": "Queued",
            "running": "Running",
            "completed": "Completed",
            "failed": "Failed",
        }.get(normalized, "Failed")
        now = self.completed_at or time.time()
        elapsed = max(0, int(now - self.started_at))
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started_at))
        commit = sanitize_github_output(self.reviewed_commit or "pending", self.config)
        command = sanitize_github_output(self.command, self.config)
        lines = [
            STATUS_MARKER,
            f"## {REVIEW_DISPLAY_NAME} — {state_label}",
            "",
            f"- Exact reviewed commit: `{commit}`.",
            f"- Trigger: `{command}`.",
            f"- Started: `{started}`.",
            f"- Elapsed: `{elapsed}s`.",
            *workflow_run_status_lines(self.config),
        ]
        if self.formal_review_url:
            safe_url = sanitize_github_output(self.formal_review_url, self.config)
            review_label = str(self.formal_review_id or "review")
            lines.append(f"- Formal GitHub review: [`{review_label}`]({safe_url}) — authoritative review artifact.")
        else:
            lines.append("- Formal GitHub review: pending; the status comment is progress-only.")
        if final_lines:
            lines.extend(["", *final_lines])
        if self.steps:
            lines.extend(["", "<details>", "<summary>Recent progress</summary>", ""])
            for stage, message in self.steps[-8:]:
                lines.append(f"- `{sanitize_public_identity(stage)}`: {message}")
            lines.extend(["", "</details>"])
        return github_safe_body("\n".join(lines), limit=12000)

    def _update_comment(self, body: str, create_if_missing: bool = True, force: bool = False) -> None:
        self._status_comment.comment_id = int(self.comment_id or self._status_comment.comment_id or 0)
        self._status_comment.publish(body, create_if_missing=create_if_missing, force=force)
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
