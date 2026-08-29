class ProgressReporter:
    def __init__(self, gh: GitHubClient, issue_number: int, command: str, config: Config) -> None:
        self.gh = gh
        self.issue_number = issue_number
        self.command = command
        self.config = config
        self.comment_id = 0
        self.steps: list[tuple[str, str]] = []

    def start(self) -> None:
        self._record("started", "accepted operator review command and initialized progress reporting")
        if not self.config.post_progress_comment:
            return
        try:
            comment = self.gh.create_issue_comment(self.issue_number, self._body("running"))
            self.comment_id = int(comment.get("id", 0))
        except Exception as exc:
            print(f"WARN: unable to create progress comment: {exc}", file=sys.stderr, flush=True)

    def update(self, stage: str, message: str) -> None:
        self._record(stage, message)
        self._update_comment(self._body("running"))

    def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
        plural = "finding" if findings_count == 1 else "findings"
        self._record("completed", f"posted GitHub review; {findings_count} inline {plural}; event={review_event}")
        self._update_comment(
            self._body(
                "completed",
                final_lines=[
                    f"- Result: GitHub review posted with `{findings_count}` inline {plural}.",
                    f"- Review event: `{review_event}`.",
                ],
            )
        )

    def fail(self, message: str) -> None:
        safe_message = sanitize_github_output(message, self.config)
        self._record("failed", safe_message[:500])
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
        lines = [
            MARKER,
            f"{REVIEW_DISPLAY_NAME} {state}.",
            "",
            f"- Command: `{self.command}`.",
            f"- Debug progress: `{str(getattr(self.config, 'debug', False)).lower()}`.",
            *workflow_run_status_lines(self.config),
            "- Branch changes: none; this workflow only posts review output.",
            "- Gate role: internal review-assist signal before any separately approved external review request.",
        ]
        if final_lines:
            lines.extend(["", *final_lines])
        lines.extend(["", "Progress:"])
        for stage, message in self.steps[-12:]:
            lines.append(f"- `{sanitize_public_identity(stage)}`: {message}")
        return github_safe_body("\n".join(lines), limit=12000)

    def _update_comment(self, body: str, create_if_missing: bool = False, force: bool = False) -> None:
        if not force and not self.config.post_progress_comment:
            return
        try:
            if self.comment_id:
                self.gh.update_issue_comment(self.comment_id, body)
            elif create_if_missing:
                comment = self.gh.create_issue_comment(self.issue_number, body)
                self.comment_id = int(comment.get("id", 0))
        except Exception as exc:
            print(f"WARN: unable to update progress comment: {exc}", file=sys.stderr, flush=True)


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


