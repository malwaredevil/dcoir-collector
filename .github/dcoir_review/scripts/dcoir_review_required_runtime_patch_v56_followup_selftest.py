#!/usr/bin/env python3
"""Focused regressions for v56 recursive batch telemetry and identity mapping."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class FakeGH:
    def get_pr_diff(self, pr_number: int) -> str:
        assert pr_number == 526
        return (
            "diff --git a/a.py b/a.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1 +1 @@\n"
            "-value = 0\n"
            "+value = 1\n"
        )


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def _finding(path: str) -> dict:
    return {
        "title": f"Fix {path}",
        "severity": "high",
        "confidence": 0.95,
        "path": path,
        "line": 1,
        "body": "Verifier-supported defect.",
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
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)

    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v53 = importlib.import_module("dcoir_review_required_runtime_patch_v53")
    v56 = importlib.import_module("dcoir_review_required_runtime_patch_v56")
    batch = importlib.import_module("dcoir_review_required_runtime_patch_v56_batch")
    repair = importlib.import_module("dcoir_review_required_runtime_patch_v56_repair")

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    config.fix_synthesis_enabled = True
    config.fix_synthesis_max_findings = 8
    config.fix_synthesis_min_confidence = 0.80
    config.repair_critic_batching_enabled = True
    config.repair_critic_batch_max_findings = 8

    original_verify = v21.verify_findings_for_publication
    original_prepare = repair.prepare_candidate
    original_run_group = batch.run_group
    original_counters = v53._repair_result_counters
    original_write_metrics = v53._write_metrics
    original_debug = review.hardened.write_debug_json_artifact_safely

    debug: list[tuple[str, dict]] = []

    def fake_verify(mod, findings, gh, pr, cfg, reporter):
        return [dict(item) for item in findings]

    def fake_prepare(mod, ordinal, finding, gh, head_sha, pr_diff, cfg, file_cache):
        return None, {
            "ordinal": ordinal,
            "finding": finding,
            "author": _author(finding["path"]),
            "author_model": "anthropic/claude-opus-5",
            "author_tier": "default",
            "critic_model": "openai/gpt-5.6-sol-pro",
            "critic_item_id": f"C{ordinal:02d}-telemetry",
        }

    def fake_run_group(mod, group, file_cache, right_line_index, cfg):
        # Model the real recursive split shape: one top-level chunk becomes two
        # child critic requests. The parent must account for both executed batches.
        return [(item["ordinal"], {"ordinal": item["ordinal"]}) for item in group], 2

    def fake_counters(item):
        return {
            "repair_sets": 0,
            "native_blocks": 0,
            "guidance_blocks": 0,
            "declined": 0,
            "precritic_declined": 0,
            "critic_rejected": 0,
            "postcritic_declined": 0,
        }

    def fake_debug(cfg, path, payload):
        debug.append((path, dict(payload)))

    v21.verify_findings_for_publication = fake_verify
    repair.prepare_candidate = fake_prepare
    batch.run_group = fake_run_group
    v53._repair_result_counters = fake_counters
    v53._write_metrics = lambda *args, **kwargs: None
    review.hardened.write_debug_json_artifact_safely = fake_debug
    try:
        result = v56.synthesize_verified_repair_sets(
            review,
            [_finding("a.py"), _finding("b.py")],
            FakeGH(),
            {"number": 526, "head": {"sha": "deadbeef"}},
            {},
            config,
            Reporter(),
        )
        assert len(result) == 2
        metrics = [payload for path, payload in debug if path == "metadata/repair-v56-batching.json"][-1]
        assert metrics["critic_candidates"] == 2
        assert metrics["critic_calls"] == 2
        assert metrics["critic_batches"] == 2
    finally:
        v21.verify_findings_for_publication = original_verify
        repair.prepare_candidate = original_prepare
        batch.run_group = original_run_group
        v53._repair_result_counters = original_counters
        v53._write_metrics = original_write_metrics
        review.hardened.write_debug_json_artifact_safely = original_debug

    # Prove reversed batch output is mapped by critic_item_id, not list position.
    original_batch_prompt = batch.batch_prompt
    original_review = review.hardened.openrouter_review
    original_debug = review.hardened.write_debug_json_artifact_safely
    original_finalize = repair.finalize_candidate

    first = {
        "ordinal": 1,
        "finding": _finding("a.py"),
        "author": _author("a.py"),
        "author_model": "anthropic/claude-opus-5",
        "author_tier": "default",
        "critic_model": "openai/gpt-5.6-sol-pro",
        "critic_item_id": "C01-alpha",
    }
    second = {
        "ordinal": 2,
        "finding": _finding("b.py"),
        "author": _author("b.py"),
        "author_model": "anthropic/claude-opus-5",
        "author_tier": "default",
        "critic_model": "openai/gpt-5.6-sol-pro",
        "critic_item_id": "C02-beta",
    }

    def fake_batch_prompt(mod, pending, file_cache, cfg):
        return "bounded identity test prompt"

    def fake_openrouter(prompt, schema, cfg, reporter=None):
        assert schema is batch.BATCH_CRITIC_SCHEMA
        return {
            "results": [
                {
                    "critic_item_id": "C02-beta",
                    "accepted": False,
                    "confidence": 0.91,
                    "reason": "reject-beta",
                },
                {
                    "critic_item_id": "C01-alpha",
                    "accepted": True,
                    "confidence": 0.99,
                    "reason": "accept-alpha",
                },
            ]
        }, "openai/gpt-5.6-sol-pro", "default"

    def fake_finalize(mod, pending, decision, critic_model, critic_tier, right_line_index, file_cache, cfg, batch_size):
        return {
            "critic_item_id": pending["critic_item_id"],
            "accepted": decision[0],
            "confidence": decision[1],
            "reason": decision[2],
            "batch_size": batch_size,
        }

    batch.batch_prompt = fake_batch_prompt
    review.hardened.openrouter_review = fake_openrouter
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    repair.finalize_candidate = fake_finalize
    try:
        results, calls = batch.run_group(review, [first, second], {}, {}, config)
        assert calls == 1
        mapped = {ordinal: item for ordinal, item in results}
        assert mapped[1]["critic_item_id"] == "C01-alpha"
        assert mapped[1]["accepted"] is True
        assert mapped[1]["reason"] == "accept-alpha"
        assert mapped[2]["critic_item_id"] == "C02-beta"
        assert mapped[2]["accepted"] is False
        assert mapped[2]["reason"] == "reject-beta"
        assert mapped[1]["batch_size"] == 2
        assert mapped[2]["batch_size"] == 2
    finally:
        batch.batch_prompt = original_batch_prompt
        review.hardened.openrouter_review = original_review
        review.hardened.write_debug_json_artifact_safely = original_debug
        repair.finalize_candidate = original_finalize

    print(
        "dcoir_review_required_runtime_patch_v56_followup_selftest passed: recursive split telemetry and reversed identity dispositions remain exact"
    )


if __name__ == "__main__":
    main()
