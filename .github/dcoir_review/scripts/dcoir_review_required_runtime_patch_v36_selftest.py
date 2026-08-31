#!/usr/bin/env python3
"""Regression checks for DCOIR Review v36 coordinated repair sets."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def _edit(path: str, start: int, end: int, original: str, replacement: str, purpose: str = "fix") -> dict:
    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "original": original,
        "replacement": replacement,
        "purpose": purpose,
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v36" in names
    assert names.index("dcoir_review_required_runtime_patch_v35") < names.index("dcoir_review_required_runtime_patch_v36")
    assert names.index("dcoir_review_required_runtime_patch_v36") < names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v30 = importlib.import_module("dcoir_review_required_runtime_patch_v30")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")
    assert getattr(review, v36.APPLIED_MARKER, False) is True
    assert hasattr(review, "build_review_comments_for_finding")

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False
    assert set(v36.REPAIR_SET_AUTHOR_SCHEMA["properties"]["action"]["enum"]) == {"repair_set", "no_safe_repair"}
    assert v36.REPAIR_SET_AUTHOR_SCHEMA["properties"]["edits"]["maxItems"] >= 3
    critic_after_opus = v36._repair_critic_config(config, "anthropic/claude-opus-5")
    assert critic_after_opus.model_stack == ["openai/gpt-5.6-sol-pro"]
    assert critic_after_opus.model == "openai/gpt-5.6-sol-pro"
    critic_after_sol = v36._repair_critic_config(config, "openai/gpt-5.6-sol-pro")
    assert critic_after_sol.model_stack == ["anthropic/claude-opus-5"]
    assert critic_after_sol.model == "anthropic/claude-opus-5"
    assert config.model_stack[0] == "anthropic/claude-opus-5"  # shared config was not mutated
    source = Path(".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36.py").read_text(encoding="utf-8")
    for phrase in ("contiguous multi-line block", "non-contiguous ranges", "several files", "exact current text"):
        assert phrase in source
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    files = {"probe.py": "x = 1\ny = 2\nz = x + y\n"}
    edits = [_edit("probe.py", 1, 2, "x = 1\ny = 2", "x = 2\ny = 3", "correct both inputs")]
    updated, reason = v36._apply_edits_to_files(files, edits)
    assert reason == ""
    assert updated["probe.py"].startswith("x = 2\ny = 3\n")

    edits = [
        _edit("probe.py", 1, 1, "x = 1", "x = 10", "first range"),
        _edit("probe.py", 3, 3, "z = x + y", "z = (x + y) * 2", "second range"),
    ]
    updated, reason = v36._apply_edits_to_files(files, edits)
    assert reason == ""
    assert "x = 10" in updated["probe.py"] and "* 2" in updated["probe.py"]

    files2 = {"a.py": "VALUE = 1\n", "b.py": "from a import VALUE\nRESULT = VALUE\n"}
    edits2 = [
        _edit("a.py", 1, 1, "VALUE = 1", "VALUE = 2", "producer"),
        _edit("b.py", 2, 2, "RESULT = VALUE", "RESULT = VALUE * 2", "consumer"),
    ]
    updated, reason = v36._apply_edits_to_files(files2, edits2)
    assert reason == "" and set(updated) == {"a.py", "b.py"}

    overlapping = [
        _edit("probe.py", 1, 2, "x = 1\ny = 2", "x = 2\ny = 3"),
        _edit("probe.py", 2, 3, "y = 2\nz = x + y", "y = 4\nz = x + y"),
    ]
    _updated, reason = v36._apply_edits_to_files(files, overlapping)
    assert "overlapping" in reason
    stale = [_edit("probe.py", 1, 1, "x = 999", "x = 2")]
    _updated, reason = v36._apply_edits_to_files(files, stale)
    assert "did not match exact head text" in reason
    broken = [_edit("probe.py", 1, 1, "x = 1", "if (")]
    _updated, reason = v36._apply_edits_to_files(files, broken)
    assert "Python syntax invalid" in reason

    right_lines = {("probe.py", 1): 1, ("probe.py", 2): 2, ("probe.py", 3): 3, ("other.py", 5): 4}
    annotated = v36._annotate_native_eligibility(
        [
            _edit("probe.py", 1, 3, "a\nb\nc", "d\ne\nf"),
            _edit("other.py", 5, 5, "old", "new"),
            _edit("outside.py", 9, 9, "old", "new"),
        ],
        right_lines,
    )
    assert [item["native_suggestion"] for item in annotated] == [True, True, False]

    finding = {
        "title": "Coordinated bug",
        "severity": "high",
        "confidence": 0.98,
        "path": "probe.py",
        "line": 2,
        "body": "The verified defect requires coordinated edits.",
        "validation": "python3 -m py_compile probe.py",
        v25.REPAIR_MARKER: {
            "version": v36.VERSION,
            "outcome": v36.REPAIR_SET_OUTCOME,
            "repair_set_id": "R01",
            "edits": annotated,
        },
    }
    comments = v36.build_review_comments_for_finding(review, finding, "model", config)
    assert len(comments) == 2
    assert comments[0]["path"] == "probe.py"
    assert comments[0]["start_line"] == 1 and comments[0]["line"] == 3
    assert comments[0]["start_side"] == "RIGHT" and comments[0]["side"] == "RIGHT"
    assert "```suggestion\nd\ne\nf\n```" in comments[0]["body"]
    assert "outside.py:9-9" in comments[0]["body"]
    assert comments[1]["path"] == "other.py" and comments[1]["line"] == 5
    assert "start_line" not in comments[1]

    deterministic = dict(finding)
    deterministic["title"] = "MODEL-TAMPERED SENTINEL TITLE"
    deterministic["body"] = "MODEL-TAMPERED SENTINEL BODY"
    deterministic[v30.v21.VERIFIER_MARKER] = {
        "mode": "deterministic-core-sentinel",
        "supported": True,
        "kind": v30.v20.PYTHON_TRUTHY_LITERAL_BRANCH,
    }
    deterministic_comments = v36.build_review_comments_for_finding(review, deterministic, "model", config)
    canonical_title, canonical_body, _notes = v30.v20._template_for_kind(v30.v20.PYTHON_TRUTHY_LITERAL_BRANCH)
    assert canonical_title in deterministic_comments[0]["body"]
    assert canonical_body in deterministic_comments[0]["body"]
    assert "MODEL-TAMPERED SENTINEL" not in deterministic_comments[0]["body"]

    # Exercise the actual active production synthesis wrapper chain without
    # network access. This catches later overlays that might accidentally rewrite
    # or bypass v36 after its helpers have individually passed.
    pipeline_finding = {
        "title": "Two-line coordinated defect",
        "severity": "high",
        "confidence": 0.99,
        "path": "probe.py",
        "line": 1,
        "body": "The two inputs must be corrected together.",
        "validation": "python3 -m py_compile probe.py",
    }
    pipeline_diff = (
        "diff --git a/probe.py b/probe.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/probe.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+x = 1\n"
        "+y = 2\n"
        "+z = x + y\n"
    )

    class _FakeGH:
        def get_pr_diff(self, pr_number):
            assert pr_number == 448
            return pipeline_diff

    class _PipelineReporter:
        def __init__(self):
            self.events = []

        def update(self, stage, message):
            self.events.append((stage, message))

    original_verify = v30.v21.verify_findings_for_publication
    original_openrouter = review.hardened.openrouter_review
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    model_calls = []

    def _fake_verify(mod, findings, gh, pr, cfg, reporter):
        assert pr["number"] == 448
        return [dict(item) for item in findings]

    def _fake_openrouter(prompt, schema_arg, config_arg, reporter=None):
        title = str(schema_arg.get("title", ""))
        model_calls.append((title, list(config_arg.model_stack)))
        if title == "DCOIR Verified Repair Set Author":
            return (
                {
                    "defect_present": True,
                    "action": "repair_set",
                    "edits": [
                        {
                            "path": "probe.py",
                            "start_line": 1,
                            "end_line": 2,
                            "original": "x = 1\ny = 2",
                            "replacement": "x = 2\ny = 3",
                            "purpose": "Correct the coupled inputs together.",
                        }
                    ],
                    "confidence": 0.99,
                    "display_title": "Correct coupled inputs atomically",
                    "display_body": "Both lines participate in the verified defect and must change together.",
                    "rationale": "The demonstrated counterexample is removed only when both values are corrected.",
                    "validation": "python3 -m py_compile probe.py",
                },
                "anthropic/claude-opus-5",
                "tier-author",
            )
        if title == "DCOIR Verified Repair Set Critic":
            assert config_arg.model_stack == ["openai/gpt-5.6-sol-pro"]
            return (
                {"accepted": True, "confidence": 0.99, "reason": "Complete and minimal coordinated repair."},
                "openai/gpt-5.6-sol-pro",
                "tier-critic",
            )
        raise AssertionError(f"unexpected schema title: {title}")

    v30.v21.verify_findings_for_publication = _fake_verify
    review.hardened.openrouter_review = _fake_openrouter
    review.fetch_pr_file_text = lambda gh, target, head: "x = 1\ny = 2\nz = x + y\n"
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    pipeline_reporter = _PipelineReporter()
    try:
        pipeline_result = review.synthesize_fixes_for_findings(
            [pipeline_finding],
            _FakeGH(),
            {"number": 448, "head": {"sha": "deadbeef"}},
            {},
            config,
            pipeline_reporter,
        )
    finally:
        v30.v21.verify_findings_for_publication = original_verify
        review.hardened.openrouter_review = original_openrouter
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug

    assert len(pipeline_result) == 1
    pipeline_marker = pipeline_result[0][v25.REPAIR_MARKER]
    assert pipeline_marker["version"] == v36.VERSION
    assert pipeline_marker["outcome"] == v36.REPAIR_SET_OUTCOME
    assert pipeline_marker["edit_count"] == 1
    assert pipeline_marker["native_suggestion_count"] == 1
    assert pipeline_marker["author_model"] == "anthropic/claude-opus-5"
    assert pipeline_marker["critic_model"] == "openai/gpt-5.6-sol-pro"
    assert model_calls[0][0] == "DCOIR Verified Repair Set Author"
    assert model_calls[1] == ("DCOIR Verified Repair Set Critic", ["openai/gpt-5.6-sol-pro"])
    pipeline_comments = review.build_review_comments_for_finding(pipeline_result[0], "model", config)
    assert len(pipeline_comments) == 1
    assert pipeline_comments[0]["start_line"] == 1
    assert pipeline_comments[0]["line"] == 2
    assert "```suggestion\nx = 2\ny = 3\n```" in pipeline_comments[0]["body"]

    absent_author = {
        "defect_present": False,
        "confidence": 0.99,
        "display_title": "No defect",
        "display_body": "The alleged defect is absent.",
    }
    suppressed = v36._declined_item(finding, absent_author, "exact evidence disproves the claim")
    assert suppressed[v25.REPAIR_MARKER]["outcome"] == v30.SUPPRESSED_OUTCOME

    publisher_before = review.build_review_comments_for_finding
    synth_before = v25.synthesize_verified_repairs
    v36.apply_pareto_context_module(review)
    assert review.build_review_comments_for_finding is publisher_before
    assert v25.synthesize_verified_repairs is synth_before

    print("dcoir_review_required_runtime_patch_v36_selftest passed")


if __name__ == "__main__":
    main()
