#!/usr/bin/env python3
"""Adversarial checks for v41 signed DCOIR frontier provenance."""

from __future__ import annotations

import importlib
import os
from types import SimpleNamespace


def main() -> None:
    state = importlib.import_module("dcoir_review_required_runtime_patch_v41_review_state")
    base_sha = "1" * 40
    reviewed_head = "a" * 40
    repo = "malwaredevil/dcoir-collector"
    pr_number = 7
    run_id = "123456"
    marker = "<!-- DCOIR Review -->"
    context_marker = "<!-- DCOIR context review -->"

    old_openrouter = os.environ.get("OPENROUTER_API_KEY")
    old_dedicated = os.environ.get("DCOIR_REVIEW_STATE_HMAC_KEY")
    os.environ["OPENROUTER_API_KEY"] = "v41-provenance-selftest-secret"
    os.environ.pop("DCOIR_REVIEW_STATE_HMAC_KEY", None)

    class FakeGitHub:
        def __init__(self, reviews, *, conclusion="success", path=state.TRUSTED_WORKFLOW_PATH, event="issue_comment", run_name=None):
            self.repo = repo
            self.reviews = list(reviews)
            self.conclusion = conclusion
            self.path = path
            self.event = event
            self.run_name = run_name or f"{state.TRUSTED_WORKFLOW_NAME} | PR #{pr_number} | malwaredevil"

        def request(self, method, path, body=None, accept="application/vnd.github+json"):
            assert method == "GET"
            assert path == f"/repos/{repo}/actions/runs/{run_id}"
            return {
                "id": int(run_id),
                "name": self.run_name,
                "path": self.path,
                "event": self.event,
                # issue_comment runs execute trusted workflow source from the
                # default branch. This deliberately must NOT equal reviewed_head.
                "head_branch": "main",
                "head_sha": "d" * 40,
                "status": "completed",
                "conclusion": self.conclusion,
                "actor": {"login": "malwaredevil"},
            }

    module = SimpleNamespace(
        base=SimpleNamespace(MARKER=marker, LEGACY_MARKERS=()),
        CONTEXT_REVIEW_MARKER=context_marker,
        list_pr_reviews=lambda gh, _number: list(gh.reviews),
    )

    try:
        provenance = state.build_review_provenance_marker(
            repo,
            pr_number,
            base_sha,
            reviewed_head,
            run_id,
            state.TRUSTED_WORKFLOW_NAME,
        )
        assert provenance.startswith(state.PROVENANCE_PREFIX)
        assert "signature=" in provenance
        body = (
            f"{marker}\n{context_marker} `diff`\n"
            f"Context readback: trusted; {state.ARCHITECTURE_CONTRACT_MARKER}; "
            f"{state.BASE_CONTRACT_PREFIX}{base_sha}; {provenance}"
        )
        valid = {
            "id": 1,
            "commit_id": reviewed_head,
            "body": body,
            "user": {"login": "github-actions[bot]"},
        }

        signature_prefix, _, _signature = provenance.rpartition("=")
        forged_provenance = f"{signature_prefix}={'0' * 64}"
        forged_body = body.replace(provenance, forged_provenance)
        forged_actions = {
            "id": 2,
            "commit_id": reviewed_head,
            "body": forged_body,
            "user": {"login": "github-actions[bot]"},
        }
        copied_human = {
            "id": 3,
            "commit_id": reviewed_head,
            "body": body,
            "user": {"login": "malwaredevil"},
        }

        # Newer copied/forged reviews cannot supersede the authentic signed state.
        gh = FakeGitHub([valid, forged_actions, copied_human])
        accepted = state.latest_compatible_context_review(module, gh, pr_number)
        assert accepted is valid

        # Shared bot identity plus public markers is insufficient without HMAC.
        assert state.latest_compatible_context_review(
            module, FakeGitHub([forged_actions]), pr_number
        ) is None

        # A valid signature is still coupled to a successful run of the exact
        # trusted DCOIR workflow/event and PR-specific run identity.
        assert state.latest_compatible_context_review(
            module, FakeGitHub([valid], conclusion="failure"), pr_number
        ) is None
        assert state.latest_compatible_context_review(
            module, FakeGitHub([valid], path=".github/workflows/other.yml"), pr_number
        ) is None
        assert state.latest_compatible_context_review(
            module, FakeGitHub([valid], event="workflow_dispatch"), pr_number
        ) is None
        assert state.latest_compatible_context_review(
            module,
            FakeGitHub([valid], run_name=f"{state.TRUSTED_WORKFLOW_NAME} | PR #8 | malwaredevil"),
            pr_number,
        ) is None

        # Signature is bound to the review commit, not GitHub Actions run.head_sha.
        wrong_head_review = dict(valid, commit_id="b" * 40)
        assert state.latest_compatible_context_review(
            module, FakeGitHub([wrong_head_review]), pr_number
        ) is None

        # If no signing secret is available, v41 produces no reusable receipt and
        # therefore falls back to cumulative review rather than trusting markers.
        os.environ.pop("OPENROUTER_API_KEY", None)
        assert state.build_review_provenance_marker(
            repo, pr_number, base_sha, reviewed_head, run_id, state.TRUSTED_WORKFLOW_NAME
        ) == ""
    finally:
        if old_openrouter is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = old_openrouter
        if old_dedicated is None:
            os.environ.pop("DCOIR_REVIEW_STATE_HMAC_KEY", None)
        else:
            os.environ["DCOIR_REVIEW_STATE_HMAC_KEY"] = old_dedicated

    print("dcoir_review_required_runtime_patch_v41_provenance_selftest passed")


if __name__ == "__main__":
    main()
