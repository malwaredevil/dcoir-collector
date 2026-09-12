from __future__ import annotations

import sys
from typing import Any

STATUS_MARKER = "<!-- dcoir-review-status:v1 -->"
MAX_COMMENT_PAGES = 20


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
        self.last_error = ""

    def discover(self) -> int:
        """Reuse the newest bot-authored canonical status comment on this PR."""
        matches: list[int] = []
        try:
            repo = str(getattr(self.gh, "repo", "") or "").strip()
            if not repo:
                return 0
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
                if len(batch) < 100:
                    break
        except Exception as exc:
            self._warn(f"unable to discover canonical status comment: {exc}")
            return 0

        if not matches:
            return 0
        self.comment_id = max(matches)
        return self.comment_id

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
                self.comment_id = int(comment.get("id", 0) or 0)
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
