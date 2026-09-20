from __future__ import annotations

import sys
from typing import Any

STATUS_MARKER = "<!-- dcoir-review-status:v1 -->"
MAX_COMMENT_PAGES = 20
TRUSTED_STATUS_AUTHOR = "github-actions[bot]"
TRUSTED_STATUS_AUTHOR_CANONICAL = TRUSTED_STATUS_AUTHOR.strip().lower()


def _is_trusted_status_author(comment: Any) -> bool:
    if not isinstance(comment, dict):
        return False
    user = comment.get("user")
    if not isinstance(user, dict):
        return False
    login = str(user.get("login", "") or "").strip().lower()
    account_type = str(user.get("type", "") or "").strip().lower()
    return account_type == "bot" and login == TRUSTED_STATUS_AUTHOR_CANONICAL


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
                    if not _is_trusted_status_author(comment):
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
        """Reuse the earliest trusted-publisher canonical status comment on this PR."""
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
