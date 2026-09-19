from dcoir_review.status import (
    MutableReviewStatusComment,
    STATUS_MARKER,
    completed_status_metadata,
    encode_status_metadata,
    finding_identity,
    normalize_severity,
    parse_status_metadata,
    render_status_overview,
)


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

    def start(self) -> None:
        discovered = self._status_comment.discover()
        if discovered:
            self.comment_id = discovered
            self._previous_status_metadata = parse_status_metadata(
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
        self.context_mode = sanitize_github_output(str(context_mode or "").strip(), self.config)

    def set_changed_files(self, files: Any) -> None:
        normalized: list[dict[str, Any]] = []
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "path": sanitize_github_output(str(item.get("filename", "") or ""), self.config),
                        "status": sanitize_github_output(str(item.get("status", "") or "modified"), self.config),
                        "additions": int(item.get("additions", 0) or 0),
                        "deletions": int(item.get("deletions", 0) or 0),
                    }
                )
        self.changed_files = normalized

    def set_findings(self, findings: Any) -> None:
        normalized: list[dict[str, Any]] = []
        if isinstance(findings, list):
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                try:
                    line = int(finding.get("line", 0) or 0)
                except (TypeError, ValueError):
                    line = 0
                item = {
                    "title": sanitize_github_output(
                        str(finding.get("title", "") or "DCOIR Review finding"),
                        self.config,
                    ),
                    "severity": normalize_severity(finding.get("severity")),
                    "path": sanitize_github_output(str(finding.get("path", "") or ""), self.config),
                    "line": line,
                    "url": "",
                }
                item["identity"] = finding_identity(item)
                normalized.append(item)
        self.findings = normalized

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
                f"/repos/{repo}/pulls/{self.issue_number}/reviews/{self.formal_review_id}/comments?per_page=100",
            )
        except Exception as exc:
            print(
                f"WARN: unable to read back formal review comments for status overview: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return
        if not isinstance(comments, list):
            return
        unused = list(self.findings)
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            path = str(comment.get("path", "") or "").strip()
            try:
                line = int(comment.get("line", 0) or comment.get("original_line", 0) or 0)
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
            match["url"] = str(comment.get("html_url", "") or self.formal_review_url).strip()
            unused.remove(match)
        for item in unused:
            if not item.get("url"):
                item["url"] = self.formal_review_url

    def update(self, stage: str, message: str) -> None:
        self._record(stage, message)
        normalized_stage = sanitize_public_identity(str(stage or "").strip())
        self.public_progress = self._public_progress_for_stage(normalized_stage)
        if normalized_stage == self._last_published_stage:
            return
        self._last_published_stage = normalized_stage
        self._update_comment(self._body("running"))

    def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
        self.model_used = sanitize_github_output(str(model_used or ""), self.config)
        self.review_event = sanitize_github_output(str(review_event or ""), self.config)
        plural = "finding" if findings_count == 1 else "findings"
        self.completed_at = time.time()
        self.public_progress = "Review completed"
        self._record("completed", f"posted GitHub review; {findings_count} inline {plural}; event={review_event}")
        self._last_published_stage = "completed"
        self._update_comment(
            self._body(
                "completed",
                final_lines=[
                    f"- Result: GitHub review posted with \`{findings_count}\` inline {plural}.",
                    f"- Review event: \`{review_event}\`.",
                ],
            ),
            create_if_missing=True,
            force=True,
        )

    def fail(self, message: str) -> None:
        safe_message = sanitize_github_output(message, self.config)
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
                    "\`\`\`text",
                    safe_message[:4000],
                    "\`\`\`",
                ],
            ),
            create_if_missing=True,
            force=True,
        )

    def _record(self, stage: str, message: str) -> None:
        safe_message = sanitize_github_output(message, self.config)
        self.steps.append((stage, safe_message))
        emit_status(stage, safe_message)

    def _public_progress_for_stage(self, stage: str) -> str:
        value = str(stage or "").lower()
        if "github-review" in value or "publish" in value:
            return "Publishing the GitHub review"
        if any(token in value for token in ("normalize", "verif", "repair", "adjudication", "gate")):
            return "Validating review findings"
        if any(token in value for token in ("provider", "prompt", "semantic", "risk", "per-file", "review-mode")):
            return "Reviewing changed code"
        if any(token in value for token in ("github", "context", "assist", "reaction")):
            return "Preparing review context"
        return "Review in progress"

    def _prior_completed(self) -> dict[str, Any]:
        return completed_status_metadata(self._previous_status_metadata)

    def _open_findings(self) -> list[dict[str, Any]]:
        current = [dict(item) for item in self.findings]
        known = {finding_identity(item) for item in current if finding_identity(item)}
        state = self.gate_state if isinstance(self.gate_state, dict) else {}
        if str(state.get("gate_status", "") or "") != "blocked":
            return current
        prior = self._prior_completed()
        prior_findings = [
            dict(item)
            for item in prior.get("open_findings", [])
            if isinstance(item, dict)
        ]
        by_location = {
            (str(item.get("path", "") or ""), int(item.get("line", 0) or 0)): item
            for item in prior_findings
        }
        for record in state.get("unresolved_findings", []) or []:
            if not isinstance(record, dict) or record.get("status") != "carried-unresolved":
                continue
            path = str(record.get("path", "") or "")
            try:
                line = int(record.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            item = dict(by_location.get((path, line), {}))
            if not item:
                item = {
                    "title": "Prior verifier-supported finding remains unresolved",
                    "severity": "medium",
                    "path": path,
                    "line": line,
                    "url": self.formal_review_url,
                }
            item["carried"] = True
            identity = finding_identity(item)
            if identity and identity in known:
                continue
            if identity:
                known.add(identity)
            current.append(item)
        return current

    def _snapshot(self, state: str) -> dict[str, Any]:
        return {
            "schema": "dcoir_review_status_overview_v1",
            "state": str(state or "").strip().lower(),
            "pr_number": int(self.issue_number),
            "command": sanitize_github_output(self.command, self.config),
            "workflow_run_id": sanitize_github_output(workflow_run_id(), self.config),
            "workflow_run_url": sanitize_github_output(workflow_run_url(), self.config),
            "reviewed_head_sha": sanitize_github_output(self.reviewed_commit or "pending", self.config),
            "context_mode": self.context_mode,
            "model_outcome": self.model_used,
            "review_event": self.review_event,
            "formal_review_id": int(self.formal_review_id or 0),
            "formal_review_url": sanitize_github_output(self.formal_review_url, self.config),
            "gate_status": sanitize_github_output(str(self.gate_state.get("gate_status", "") or ""), self.config),
            "finding_count": len(self._open_findings()),
            "open_findings": self._open_findings(),
            "changed_files": [dict(item) for item in self.changed_files],
            "progress": sanitize_github_output(self.public_progress, self.config),
        }

    def _body(self, state: str, final_lines: list[str] | None = None) -> str:
        if bool(getattr(self.config, "debug", False)):
            return self._debug_body(state, final_lines=final_lines)
        return render_status_overview(self._snapshot(state), self._prior_completed())

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
        commit = sanitize_github_output(self.reviewed_commit or "pending", self.config)
        command = sanitize_github_output(self.command, self.config)
        lines = [
            STATUS_MARKER,
            encode_status_metadata(self._snapshot(state)),
            f"## {REVIEW_DISPLAY_NAME} — {state_label}",
            "",
            f"- Exact reviewed commit: \`{commit}\`.",
            f"- Trigger: \`{command}\`.",
            f"- Started: \`{started}\`.",
            f"- Elapsed: \`{elapsed}s\`.",
            *workflow_run_status_lines(self.config),
        ]
        if self.formal_review_url:
            safe_url = sanitize_github_output(self.formal_review_url, self.config)
            review_label = str(self.formal_review_id or "review")
            lines.append(f"- Formal GitHub review: [\`{review_label}\`]({safe_url}) — authoritative review artifact.")
        else:
            lines.append("- Formal GitHub review: pending; the status comment is progress-only.")
        if self.model_used:
            lines.append(f"- Provider/model outcome: \`{self.model_used}\`.")
        if self.context_mode:
            lines.append(f"- Context mode: \`{self.context_mode}\`.")
        if final_lines:
            lines.extend(["", *final_lines])
        if self.steps:
            lines.extend(["", "<details open>", "<summary>Detailed progress and diagnostics</summary>", ""])
            for stage, message in self.steps:
                lines.append(f"- \`{sanitize_public_identity(stage)}\`: {message}")
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
