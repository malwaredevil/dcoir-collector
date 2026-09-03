#!/usr/bin/env python3
"""Regression checks for Architecture-B fail-closed semantic-result reuse (v43)."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def build_fixture():
    v43 = importlib.import_module("dcoir_review_required_runtime_patch_v43")
    reuse = importlib.import_module("dcoir_review_required_runtime_patch_v43_reuse")
    debug_payloads: dict[str, object] = {}
    reporter_events: list[tuple[str, str]] = []
    provider_calls: list[str] = []

    config = SimpleNamespace(
        model="anthropic/claude-opus-5",
        model_stack=["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"],
        minimum_confidence=0.70,
        per_file_first_pass_review=True,
        max_prompt_chars=120000,
    )
    pr = {
        "number": 7,
        "title": "Reuse test",
        "base": {"ref": "main", "sha": "1" * 40},
        "head": {"ref": "feature", "sha": "3" * 40},
    }
    context = {
        "path": "src/a.py",
        "item": {
            "filename": "src/a.py",
            "status": "modified",
            "sha": "a" * 40,
            "patch": "@@ -1 +1 @@\n-old\n+new",
        },
        "text": "value = 'new'\n",
    }
    schema = {"type": "object", "properties": {"findings": {"type": "array"}}}
    sentinel = SimpleNamespace(path="src/a.py", line=1)

    def build_prompt(pr_arg, item, file_text, diff, config_arg, path_sentinels, review_mode):
        return "|".join(
            (
                str(pr_arg.get("number")),
                str(pr_arg.get("title")),
                str(item.get("filename")),
                str(item.get("patch")),
                file_text,
                str(config_arg.minimum_confidence),
                ",".join(str(getattr(value, "line", "")) for value in path_sentinels),
                review_mode,
                diff,
            )
        )

    def original_single(index, context_arg, pr_arg, diff, schema_arg, config_arg, risk_sentinels, review_mode):
        path = str(context_arg["path"])
        provider_calls.append(path)
        return {
            "path": path,
            "prompt_chars": 111,
            "result": {"summary": "recomputed", "findings": [{"title": "same"}]},
            "model_used": config_arg.model,
            "service_tier": "",
        }

    fake_module = SimpleNamespace()

    def original_hybrid(
        pr_arg,
        files,
        diff,
        schema_arg,
        config_arg,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        item = fake_module.review_single_file_context(
            1,
            context,
            pr_arg,
            diff,
            schema_arg,
            config_arg,
            risk_sentinels,
            review_mode,
        )
        return item["result"], item["model_used"], item["service_tier"]

    fake_module.openrouter_review_with_hybrid_first_pass = original_hybrid
    fake_module.review_single_file_context = original_single
    fake_module.build_per_file_review_prompt = build_prompt
    fake_module.hardened = SimpleNamespace(
        risk_sentinel_digest=lambda values: "risk:" + ",".join(
            f"{getattr(value, 'path', '')}:{getattr(value, 'line', '')}" for value in values
        ),
        write_debug_json_artifact_safely=lambda _config, path, value: debug_payloads.__setitem__(path, value),
    )
    reporter = SimpleNamespace(update=lambda stage, message: reporter_events.append((stage, message)))
    gh = SimpleNamespace()
    return v43, reuse, fake_module, config, pr, context, schema, [sentinel], reporter, gh, debug_payloads, reporter_events, provider_calls


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v41",
        "dcoir_review_required_runtime_patch_v42",
        "dcoir_review_required_runtime_patch_v43",
    )

    (
        v43,
        reuse,
        fake_module,
        config,
        pr,
        context,
        schema,
        risk_sentinels,
        reporter,
        gh,
        debug_payloads,
        reporter_events,
        provider_calls,
    ) = build_fixture()
    diff = "diff --git a/src/a.py b/src/a.py\n+new"
    material = reuse.reuse_material(
        fake_module, context, pr, diff, schema, config, risk_sentinels, "deep-forced"
    )
    prior_result = {"summary": "recomputed", "findings": [{"title": "same"}]}
    prior_record = {
        **material,
        "contract": reuse.REUSE_CONTRACT,
        "outcome": "complete",
        "origin_reviewed_head": "2" * 40,
        "carried_forward_head": "2" * 40,
        "prompt_chars": 111,
        "result": prior_result,
        "model_used": config.model,
        "service_tier": "",
    }
    eligible, reason = reuse.evaluate_reuse_candidate(material, prior_record, "2" * 40)
    assert eligible is True
    assert reason == "exact-semantic-input-match"

    # Deterministic material ignores dictionary insertion order when semantic values match.
    reordered_context = {
        "text": context["text"],
        "item": dict(reversed(list(context["item"].items()))),
        "path": context["path"],
    }
    reordered_pr = dict(reversed(list(pr.items())))
    reordered = reuse.reuse_material(
        fake_module,
        reordered_context,
        reordered_pr,
        diff,
        dict(reversed(list(schema.items()))),
        config,
        risk_sentinels,
        "deep-forced",
    )
    assert reordered["reuse_key"] == material["reuse_key"]
    assert reordered["semantic_prompt_sha256"] == material["semantic_prompt_sha256"]

    cases = []
    changed = dict(material)
    changed["source_identity"] = "blob:" + "b" * 40
    cases.append((changed, "source-changed"))
    changed = dict(material)
    changed["runtime_version"] = "v44"
    cases.append((changed, "reviewer-runtime-changed"))
    changed = dict(material)
    changed["reviewer_fingerprint"] = "x" * 64
    cases.append((changed, "reviewer-changed"))
    changed = dict(material)
    changed["schema_sha256"] = "x" * 64
    cases.append((changed, "schema-changed"))
    changed = dict(material)
    changed["config_sha256"] = "x" * 64
    cases.append((changed, "config-changed"))
    changed = dict(material)
    changed["dependency_sha256"] = "x" * 64
    cases.append((changed, "dependency-context-changed"))
    changed = dict(material)
    changed["risk_fingerprint"] = "changed-risk"
    cases.append((changed, "risk-invariant-changed"))
    changed = dict(material)
    changed["review_mode"] = "first-pass-deep"
    cases.append((changed, "review-mode-changed"))
    for current, expected_reason in cases:
        allowed, observed_reason = reuse.evaluate_reuse_candidate(current, prior_record, "2" * 40)
        assert allowed is False
        assert observed_reason == expected_reason

    incomplete = dict(prior_record)
    incomplete["outcome"] = "failed"
    assert reuse.evaluate_reuse_candidate(material, incomplete, "2" * 40) == (
        False,
        "prior-result-incomplete",
    )
    assert reuse.evaluate_reuse_candidate(material, prior_record, "") == (
        False,
        "trusted-prior-head-missing",
    )
    assert reuse.evaluate_reuse_candidate(material, prior_record, "9" * 40) == (
        False,
        "prior-head-mismatch",
    )

    # Eligible evidence bypasses the original provider path but preserves the exact result shape.
    original_loader = reuse.trusted_prior_manifest
    try:
        reuse.trusted_prior_manifest = lambda _module, _gh, _pr: (
            {
                "contract": reuse.REUSE_CONTRACT,
                "outcome": "complete",
                "reviewed_head": "2" * 40,
                "records": [prior_record],
            },
            "2" * 40,
            "trusted-prior-manifest-loaded",
        )
        v43.apply_pareto_context_module(fake_module)
        result, model, tier = fake_module.openrouter_review_with_hybrid_first_pass(
            pr,
            [context["item"]],
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            {},
            "",
            "deep-forced",
            "",
            gh,
        )
        assert provider_calls == []
        assert result == prior_result
        assert model == config.model
        assert tier == ""
        manifest = debug_payloads[reuse.MANIFEST_PATH]
        assert manifest["outcome"] == "complete"
        assert manifest["records"][0]["result"] == prior_result
        assert manifest["records"][0]["carried_forward_head"] == "3" * 40
        assert reporter_events[-1][0] == "semantic-reuse"
        assert "reused=1" in reporter_events[-1][1]

        # A source change invalidates the record and calls the original provider path exactly once.
        context["item"]["sha"] = "b" * 40
        context["text"] = "value = 'newer'\n"
        result, _model, _tier = fake_module.openrouter_review_with_hybrid_first_pass(
            pr,
            [context["item"]],
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            {},
            "",
            "deep-forced",
            "",
            gh,
        )
        assert provider_calls == ["src/a.py"]
        assert result == prior_result
        assert "recomputed=1" in reporter_events[-1][1]
    finally:
        reuse.trusted_prior_manifest = original_loader

    # Deleted files are explicitly non-applicable rather than reusable.
    state = {
        "decisions": {},
        "records": {},
        "load_reason": "trusted-prior-manifest-loaded",
    }
    gh_with_ledger = SimpleNamespace(
        _dcoir_v42_semantic_review_ledger={
            "telemetry": {},
            "reuse": {},
            "file_records": [
                {"path": "src/old.py", "status": "removed", "reuse_allowed": False}
            ],
        }
    )
    v43._apply_ledger_telemetry(fake_module, gh_with_ledger, config, state)
    ledger = gh_with_ledger._dcoir_v42_semantic_review_ledger
    assert ledger["file_records"][0]["reuse_decision"] == "not-applicable"
    assert ledger["file_records"][0]["reuse_reason"] == "deleted-file"

    # Manifest publication is success-only: a failed semantic pass cannot become reusable evidence.
    failure_debug: dict[str, object] = {}
    failing_module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")),
        review_single_file_context=lambda *_args: {},
        build_per_file_review_prompt=fake_module.build_per_file_review_prompt,
        hardened=SimpleNamespace(
            risk_sentinel_digest=lambda _values: "",
            write_debug_json_artifact_safely=lambda _config, path, value: failure_debug.__setitem__(path, value),
        ),
    )
    original_loader = reuse.trusted_prior_manifest
    try:
        reuse.trusted_prior_manifest = lambda _module, _gh, _pr: (None, "", "trusted-prior-review-missing")
        v43.apply_pareto_context_module(failing_module)
        try:
            failing_module.openrouter_review_with_hybrid_first_pass(
                pr, [], diff, schema, config, reporter, [], {}, "", "deep-forced", "", SimpleNamespace()
            )
            raise AssertionError("expected failing semantic pass")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        assert reuse.MANIFEST_PATH not in failure_debug
    finally:
        reuse.trusted_prior_manifest = original_loader

    source_root = Path(".github/dcoir_review/scripts")
    source = "".join(
        (source_root / name).read_text(encoding="utf-8")
        for name in (
            "dcoir_review_required_runtime_patch_v43.py",
            "dcoir_review_required_runtime_patch_v43_reuse.py",
        )
    )
    for required in (
        "architecture-b-semantic-result-reuse-v1",
        "dependency-context-v2",
        "exact-semantic-prompt-v1",
        "prior-result-incomplete",
        "dependency-context-changed",
        "trusted-prior-manifest-loaded",
        "semantic-result-reuse-manifest.json",
        "deleted-file",
    ):
        assert required in source
    for forbidden in (
        "openrouter.ai",
        "chat/completions",
        "git push",
        "merge_pull_request",
    ):
        assert forbidden not in source

    print("dcoir_review_required_runtime_patch_v43_selftest passed")


if __name__ == "__main__":
    main()
