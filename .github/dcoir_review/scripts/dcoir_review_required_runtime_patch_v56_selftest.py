#!/usr/bin/env python3
"""Deterministic no-inference regressions for DCOIR Review v56 critic batching."""

from __future__ import annotations

import copy
import importlib
import re

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class FakeGH:
    def __init__(self, diff: str) -> None:
        self.diff = diff
        self.diff_calls = 0

    def get_pr_diff(self, pr_number: int) -> str:
        assert pr_number == 526
        self.diff_calls += 1
        return self.diff


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def _diff(paths: list[str]) -> str:
    blocks = []
    for path in paths:
        blocks.append(
            f"diff --git a/{path} b/{path}\n"
            "index 1111111..2222222 100644\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            "@@ -1 +1 @@\n"
            "-value = 0\n"
            "+value = 1\n"
        )
    return "".join(blocks)


def _finding(path: str, confidence: float = 0.95) -> dict:
    return {
        "title": f"Fix {path}",
        "severity": "high",
        "confidence": confidence,
        "path": path,
        "line": 1,
        "body": "Verifier-supported defect.",
        "suggested_replacement": "untrusted detector text",
        "validation": f"python3 -m py_compile {path}",
    }


def _author(path: str) -> dict:
    return {
        "defect_present": True,
        "action": "repair_set",
        "edits": [
            {
                "path": path,
                "start_line": 1,
                "end_line": 1,
                "original": "value = 1",
                "replacement": "value = 2",
                "purpose": f"Repair {path}",
            }
        ],
        "confidence": 0.99,
        "display_title": f"Repair {path}",
        "display_body": "Apply the verified correction.",
        "rationale": "The replacement fixes the demonstrated defect.",
        "validation": f"python3 -m py_compile {path}",
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_telemetry_patch_module_names[-1] == "dcoir_review_required_runtime_patch_v56"

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")
    v53 = importlib.import_module("dcoir_review_required_runtime_patch_v53")
    v54 = importlib.import_module("dcoir_review_required_runtime_patch_v54")
    v56 = importlib.import_module("dcoir_review_required_runtime_patch_v56")
    batch = importlib.import_module("dcoir_review_required_runtime_patch_v56_batch")
    repair = importlib.import_module("dcoir_review_required_runtime_patch_v56_repair")
    assert getattr(review, v56.APPLIED_MARKER, False) is True

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    config.fix_synthesis_min_confidence = 0.80
    config.fix_synthesis_max_findings = 8
    config.fix_synthesis_enabled = True
    assert config.repair_critic_batching_enabled is True
    assert config.repair_critic_batch_max_findings == batch.MAX_BATCH_ITEMS
    assert v56._batch_limit(config) == batch.MAX_BATCH_ITEMS

    original_verify = v21.verify_findings_for_publication
    original_review = review.hardened.openrouter_review
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    original_v53 = v53.synthesize_verified_repair_sets

    calls: list[tuple[str, str, str]] = []
    debug: list[tuple[str, dict]] = []
    author_models: dict[str, str] = {}

    def fake_verify(mod, findings, gh, pr, cfg, reporter):
        return [dict(item) for item in findings]

    def fake_fetch(gh, path, head_sha):
        assert head_sha == "deadbeef"
        return "value = 1\n"

    def fake_debug(cfg, path, payload):
        debug.append((path, dict(payload)))

    def fake_openrouter(prompt, schema, cfg, reporter=None):
        if schema is v36.REPAIR_SET_AUTHOR_SCHEMA:
            match = re.search(r"Primary finding anchor: ([^:]+):1", prompt)
            assert match, prompt[:500]
            path = match.group(1)
            model = author_models.get(path, "anthropic/claude-opus-5")
            calls.append(("author", path, model))
            return _author(path), model, "default"
        if schema is batch.BATCH_CRITIC_SCHEMA:
            ids = re.findall(r'"critic_item_id": "([^"]+)"', prompt)
            assert len(ids) >= 2, ids
            assert getattr(cfg, batch.STAGE_LABEL_ATTR, "") == "repair-critic"
            assert v54.classify_stage(prompt, schema, cfg) == "repair-critic"
            calls.append(("batch-critic", ",".join(ids), str(cfg.model)))
            return {
                "results": [
                    {"critic_item_id": item_id, "accepted": True, "confidence": 0.99, "reason": "safe"}
                    for item_id in reversed(ids)
                ]
            }, str(cfg.model), "default"
        if schema is v36.REPAIR_SET_CRITIC_SCHEMA:
            calls.append(("single-critic", "", str(cfg.model)))
            return {"accepted": True, "confidence": 0.99, "reason": "safe"}, str(cfg.model), "default"
        raise AssertionError(f"unexpected schema: {schema.get('title') if isinstance(schema, dict) else schema}")

    v21.verify_findings_for_publication = fake_verify
    review.hardened.openrouter_review = fake_openrouter
    review.fetch_pr_file_text = fake_fetch
    review.hardened.write_debug_json_artifact_safely = fake_debug
    try:
        # Three compatible authors keep three independent author calls but collapse
        # three Sol critics into one identity-keyed batch. Reversed critic output
        # proves mapping is by ID rather than position.
        paths = ["a.py", "b.py", "c.py"]
        gh = FakeGH(_diff(paths))
        reporter = Reporter()
        calls.clear()
        debug.clear()
        author_models.clear()
        result = v56.synthesize_verified_repair_sets(
            review,
            [_finding(path) for path in paths],
            gh,
            {"number": 526, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
        assert len(result) == 3
        assert sum(1 for call in calls if call[0] == "author") == 3
        assert sum(1 for call in calls if call[0] == "batch-critic") == 1
        assert sum(1 for call in calls if call[0] == "single-critic") == 0
        markers = [item[v25.REPAIR_MARKER] for item in result]
        assert all(marker["outcome"] == v36.REPAIR_SET_OUTCOME for marker in markers)
        assert all(marker["version"] == v36.VERSION for marker in markers)
        assert all(marker["critic_batch_version"] == v56.VERSION for marker in markers)
        assert all(marker["critic_accepted"] is True for marker in markers)
        assert all(marker["critic_batch_size"] == 3 for marker in markers)
        assert len({marker["critic_item_id"] for marker in markers}) == 3
        comments = review.build_review_comments_for_finding(result[0], "test-model", config)
        assert comments
        assert "Coordinated repair set" in comments[0]["body"]
        batch_metrics = [payload for path, payload in debug if path == "metadata/repair-v56-batching.json"][-1]
        assert batch_metrics["critic_candidates"] == 3
        assert batch_metrics["critic_calls"] == 1
        assert batch_metrics["critic_batches"] == 1
        assert gh.diff_calls == 1

        # Different author families must never share a critic request. Each one-item
        # group uses the historical v36 critic schema and the opposite model family.
        paths = ["opus_author.py", "openai_author.py"]
        author_models.clear()
        author_models.update(
            {
                "opus_author.py": "anthropic/claude-opus-5",
                "openai_author.py": "openai/gpt-5.6-sol-pro",
            }
        )
        calls.clear()
        result = v56.synthesize_verified_repair_sets(
            review,
            [_finding(path) for path in paths],
            FakeGH(_diff(paths)),
            {"number": 526, "head": {"sha": "deadbeef"}},
            {},
            config,
            Reporter(),
        )
        critics = [call for call in calls if call[0] == "single-critic"]
        assert len(critics) == 2, calls
        assert {call[2] for call in critics} == {"openai/gpt-5.6-sol-pro", "anthropic/claude-opus-5"}
        assert all(item[v25.REPAIR_MARKER]["critic_accepted"] is True for item in result)

        # The identity parser isolates malformed, missing, duplicate, and unknown
        # results. Batch-schema violations fail closed before v36 acceptance logic.
        template = {
            "ordinal": 1,
            "finding": _finding("a.py"),
            "author": _author("a.py"),
            "author_model": "anthropic/claude-opus-5",
            "author_tier": "default",
            "critic_model": "openai/gpt-5.6-sol-pro",
        }
        p1 = dict(template)
        p1["critic_item_id"] = repair.critic_item_id(1, p1["finding"], p1["author"])
        p2 = copy.deepcopy(template)
        p2["ordinal"] = 2
        p2["finding"] = _finding("b.py")
        p2["author"] = _author("b.py")
        p2["critic_item_id"] = repair.critic_item_id(2, p2["finding"], p2["author"])
        parsed = batch.parse_batch(
            {
                "results": [
                    {"critic_item_id": p2["critic_item_id"], "accepted": True, "confidence": 0.99, "reason": "ok"},
                    {"critic_item_id": "unknown", "accepted": True, "confidence": 1.0, "reason": "ignored"},
                    {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 2.0, "reason": "bad"},
                ]
            },
            [p1, p2],
            review.hardened,
        )
        assert parsed[p2["critic_item_id"]][0] is True
        assert parsed[p1["critic_item_id"]][0] is False
        assert "required schema" in parsed[p1["critic_item_id"]][2]
        for invalid_item in (
            {"critic_item_id": p1["critic_item_id"], "accepted": "true", "confidence": 0.99, "reason": "bad"},
            {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 0.99},
            {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 0.99, "reason": "bad", "extra": 1},
        ):
            parsed = batch.parse_batch({"results": [invalid_item]}, [p1], review.hardened)
            assert parsed[p1["critic_item_id"]][0] is False
            assert "required schema" in parsed[p1["critic_item_id"]][2]
        parsed = batch.parse_batch(
            {
                "results": [
                    {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 0.99, "reason": "one"},
                    {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 0.99, "reason": "duplicate"},
                ]
            },
            [p1, p2],
            review.hardened,
        )
        assert parsed[p1["critic_item_id"]][0] is False
        assert "duplicate" in parsed[p1["critic_item_id"]][2]
        assert parsed[p2["critic_item_id"]][0] is False
        assert "no valid identity-bound" in parsed[p2["critic_item_id"]][2]
        parsed = batch.parse_batch(
            {
                "results": [
                    {"critic_item_id": p1["critic_item_id"], "accepted": True, "confidence": 0.99, "reason": "ok"}
                ],
                "unexpected": True,
            },
            [p1],
            review.hardened,
        )
        assert parsed[p1["critic_item_id"]][0] is False

        # Multi-item batches are measured before the historical prompt truncator.
        # A configured prompt limit therefore splits the group into historical
        # single-item critics instead of silently dropping one candidate's context.
        original_prompt_limit = config.max_prompt_chars
        try:
            config.max_prompt_chars = 1000
            full_prompt = batch.batch_prompt(
                review, [p1, p2], {"a.py": "value = 1\n", "b.py": "value = 1\n"}, config
            )
            assert len(full_prompt) > config.max_prompt_chars
            calls.clear()
            split_results, split_calls = batch.run_group(
                review,
                [p1, p2],
                {"a.py": "value = 1\n", "b.py": "value = 1\n"},
                review.base.build_diff_line_index(_diff(["a.py", "b.py"])),
                config,
            )
            assert len(split_results) == 2
            assert split_calls == 2
            assert [call[0] for call in calls] == ["single-critic", "single-critic"], calls
        finally:
            config.max_prompt_chars = original_prompt_limit

        # A single repair remains on the historical single-item critic schema.
        author_models.clear()
        calls.clear()
        result = v56.synthesize_verified_repair_sets(
            review,
            [_finding("single.py")],
            FakeGH(_diff(["single.py"])),
            {"number": 526, "head": {"sha": "deadbeef"}},
            {},
            config,
            Reporter(),
        )
        assert [call[0] for call in calls] == ["author", "single-critic"], calls
        assert result[0][v25.REPAIR_MARKER]["critic_batch_size"] == 1
        assert result[0][v25.REPAIR_MARKER]["version"] == v36.VERSION

        # The governed config exposes an operator rollback switch. Explicit disable
        # delegates to the exact v53 implementation rather than partially entering
        # v56, preserving the historical synthesis path.
        sentinel: list[bool] = []

        def fake_v53(*args, **kwargs):
            sentinel.append(True)
            return [{"delegated": True}]

        v53.synthesize_verified_repair_sets = fake_v53
        config.repair_critic_batching_enabled = False
        assert v56.synthesize_verified_repair_sets(review, [], None, {}, {}, config, Reporter()) == [{"delegated": True}]
        assert sentinel == [True]
        config.repair_critic_batching_enabled = True
    finally:
        v53.synthesize_verified_repair_sets = original_v53
        v21.verify_findings_for_publication = original_verify
        review.hardened.openrouter_review = original_review
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug

    print(
        "dcoir_review_required_runtime_patch_v56_selftest passed: config rollback, strict identity schema, pre-truncation splitting, publication compatibility, and cross-family fail-closed gates remain intact"
    )


if __name__ == "__main__":
    main()
