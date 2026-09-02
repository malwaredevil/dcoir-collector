#!/usr/bin/env python3
"""Regression checks for Architecture-B semantic ledger/context fingerprints (v42)."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    v42 = importlib.import_module("dcoir_review_required_runtime_patch_v42")
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.terminal_patch_module_names[0] == "dcoir_review_required_runtime_patch_v41"
    assert entrypoint.terminal_patch_module_names[-1] == "dcoir_review_required_runtime_patch_v42"

    calls: list[tuple] = []
    debug_payloads: dict[str, object] = {}
    reporter_events: list[tuple[str, str]] = []

    result_object = {"summary": "same semantic result", "findings": [{"title": "one"}]}

    def fake_hybrid(*args):
        calls.append(args)
        return result_object, "anthropic/claude-opus-5", ""

    def fake_append(body, review_mode, context_summary, config):
        assert review_mode == "diff"
        assert context_summary == "unchanged context summary"
        return f"{body}\n\nDCOIR context review: `{review_mode}`\nContext readback: {context_summary}"

    def fake_debug(_config, path, value):
        debug_payloads[path] = value

    fake_hardened = SimpleNamespace(
        write_debug_json_artifact_safely=fake_debug,
        risk_sentinel_digest=lambda _sentinels: "risk-digest",
        result_findings=lambda result: list(result.get("findings", [])),
    )
    fake_module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=fake_hybrid,
        append_context_to_review_body=fake_append,
        hardened=fake_hardened,
    )
    v42.apply_pareto_context_module(fake_module)
    wrapped_hybrid = fake_module.openrouter_review_with_hybrid_first_pass
    wrapped_append = fake_module.append_context_to_review_body
    wrapped_debug = fake_module.hardened.write_debug_json_artifact_safely

    # Re-applying must replace the wrapper around the saved original rather than
    # stack another semantic call or review-body marker.
    v42.apply_pareto_context_module(fake_module)
    assert fake_module.openrouter_review_with_hybrid_first_pass is not wrapped_hybrid
    assert fake_module.append_context_to_review_body is not wrapped_append
    assert fake_module.hardened.write_debug_json_artifact_safely is not wrapped_debug

    config = SimpleNamespace(
        model="anthropic/claude-opus-5",
        model_stack=["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"],
        minimum_confidence=0.70,
        per_file_first_pass_review=True,
    )
    reporter = SimpleNamespace(update=lambda stage, message: reporter_events.append((stage, message)))
    gh = SimpleNamespace(
        _dcoir_v41_review_scope={
            "source": "incremental-reviewed-head",
            "prior_reviewed_head_sha": "1" * 40,
            "current_head_sha": "2" * 40,
            "prior_reviewed_base_sha": "3" * 40,
            "current_base_sha": "3" * 40,
            "compare_status": "ahead",
            "fallback_reason": "",
        }
    )
    pr = {
        "number": 7,
        "title": "Ledger test",
        "body": "Body content",
        "base": {"ref": "main", "sha": "3" * 40},
        "head": {"ref": "feature", "sha": "2" * 40},
    }
    files = [
        {
            "filename": "src/a.py",
            "status": "modified",
            "sha": "a" * 40,
            "additions": 3,
            "deletions": 1,
            "changes": 4,
            "patch": "@@ -1 +1 @@",
        },
        {
            "filename": "src/old.py",
            "status": "removed",
            "sha": "",
            "additions": 0,
            "deletions": 5,
            "changes": 5,
        },
    ]
    schema = {"type": "object", "properties": {"findings": {"type": "array"}}}
    risk_sentinels = [SimpleNamespace(path="src/a.py", line=2)]
    line_index = {("src/a.py", 2): 9}
    args = (
        pr,
        files,
        "diff text",
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        "deep context",
        "diff",
        "unchanged context summary",
        gh,
    )
    result, model, tier = fake_module.openrouter_review_with_hybrid_first_pass(*args)
    assert result is result_object
    assert model == "anthropic/claude-opus-5"
    assert tier == ""
    assert len(calls) == 1
    assert calls[0] == args

    ledger = fake_module.semantic_review_ledger_for_client(gh)
    assert ledger["semantic_ledger_contract"] == "architecture-b-semantic-ledger-v1"
    assert ledger["architecture_contract"] == "architecture-b-v1"
    assert len(ledger["context_fingerprint"]) == 64
    assert ledger["review_surface"]["scope_source"] == "incremental-reviewed-head"
    assert ledger["review_surface"]["diff_chars"] == len("diff text")
    assert ledger["telemetry"]["reviewed_file_count"] == 2
    assert ledger["telemetry"]["reused_file_count"] == 0
    assert ledger["telemetry"]["recomputed_file_count"] == 2
    assert ledger["telemetry"]["dependency_expanded_file_count"] == 0
    assert ledger["telemetry"]["result_finding_count"] == 1
    assert ledger["telemetry"]["outcome"] == "completed"
    assert ledger["reuse"]["enabled"] is False
    assert ledger["reuse"]["eligible"] is False
    assert ledger["review_surface"]["files"][0]["prospective_reuse_key"]
    assert ledger["review_surface"]["files"][0]["reuse_allowed"] is False
    assert reporter_events and reporter_events[0][0] == "semantic-ledger"

    body = fake_module.append_context_to_review_body("BASE", "diff", "unchanged context summary", config)
    assert body.count(v42.SEMANTIC_LEDGER_MARKER_PREFIX) == 1
    assert "reuse-enabled=false" in body
    assert ledger["context_fingerprint"] in body

    fake_module.hardened.write_debug_json_artifact_safely(
        config, "metadata/review-context.json", {"existing": True}
    )
    review_context = debug_payloads["metadata/review-context.json"]
    assert review_context["existing"] is True
    assert review_context["semantic_ledger_contract"] == v42.SEMANTIC_LEDGER_CONTRACT
    assert review_context["semantic_context_fingerprint"] == ledger["context_fingerprint"]
    assert review_context["semantic_reviewed_file_count"] == 2
    assert review_context["semantic_reused_file_count"] == 0
    assert debug_payloads["metadata/semantic-review-ledger.json"]["telemetry"]["outcome"] == "completed"

    direct_a = v42.build_semantic_review_ledger(
        fake_module,
        pr,
        files,
        "diff text",
        schema,
        config,
        risk_sentinels,
        line_index,
        "deep context",
        "diff",
        "unchanged context summary",
        gh,
    )
    direct_b = v42.build_semantic_review_ledger(
        fake_module,
        dict(reversed(list(pr.items()))),
        [dict(reversed(list(item.items()))) for item in files],
        "diff text",
        dict(reversed(list(schema.items()))),
        config,
        risk_sentinels,
        line_index,
        "deep context",
        "diff",
        "unchanged context summary",
        gh,
    )
    assert direct_a["context_fingerprint"] == direct_b["context_fingerprint"]

    changed_files = [dict(item) for item in files]
    changed_files[0]["sha"] = "b" * 40
    changed = v42.build_semantic_review_ledger(
        fake_module,
        pr,
        changed_files,
        "diff text",
        schema,
        config,
        risk_sentinels,
        line_index,
        "deep context",
        "diff",
        "unchanged context summary",
        gh,
    )
    assert changed["context_fingerprint"] != direct_a["context_fingerprint"]

    changed_config = SimpleNamespace(**vars(config))
    changed_config.minimum_confidence = 0.80
    changed = v42.build_semantic_review_ledger(
        fake_module,
        pr,
        files,
        "diff text",
        schema,
        changed_config,
        risk_sentinels,
        line_index,
        "deep context",
        "diff",
        "unchanged context summary",
        gh,
    )
    assert changed["context_fingerprint"] != direct_a["context_fingerprint"]

    source = Path(".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v42.py").read_text(encoding="utf-8")
    for required in (
        "architecture-b-semantic-ledger-v1",
        "context_fingerprint",
        "prospective_reuse_key",
        "semantic-result reuse is intentionally disabled",
        "dependency-context-v1",
        "recomputed_file_count",
    ):
        assert required in source
    for forbidden in ("openrouter.ai", "chat/completions", "git push", "merge_pull_request"):
        assert forbidden not in source

    print("dcoir_review_required_runtime_patch_v42_selftest passed")


if __name__ == "__main__":
    main()
