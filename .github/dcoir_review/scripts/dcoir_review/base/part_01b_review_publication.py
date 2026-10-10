"""Review-publication fallback when GitHub cannot anchor inline comments.

GitHub rejects a whole review (HTTP 422) when any inline comment anchor cannot
be resolved against its diff. ``GitHubClient.create_review`` then re-posts once
with the findings rendered in the review body; every other 422 is re-raised.
"""

import json
from typing import Any


# GitHub reports unresolvable inline anchors as plain strings ("Line could not
# be resolved") or as structured PullRequestReviewComment field errors.
_ANCHOR_TEXT = ("could not be resolved", "must be part of the diff", "pull_request_review_thread.")
_ANCHOR_FIELDS = {"line", "path", "side", "start_line", "start_side"}


def _is_unresolvable_inline_comment_error(exc: RuntimeError, path: str) -> bool:
    try:
        errors = json.loads(str(exc).split(f"GitHub API POST {path} failed: 422 ", 1)[1])["errors"]
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    return isinstance(errors, list) and bool(errors) and all(
        any(t in e.lower() for t in _ANCHOR_TEXT) if isinstance(e, str) else isinstance(e, dict)
        and e.get("resource") == "PullRequestReviewComment" and e.get("field") in _ANCHOR_FIELDS
        for e in errors
    )


def inline_comments_as_review_body(body: str, comments: list[dict[str, Any]]) -> str:
    sections = [body.rstrip(), "", "### Findings GitHub could not anchor inline", ""]
    for comment in comments:
        location = f"{comment.get('path', '')}:{comment.get('line', '')}"
        sections.extend([f"**`{location}`**", "", str(comment.get("body", "") or "").strip(), ""])
    return github_safe_body("\n".join(sections).strip())
