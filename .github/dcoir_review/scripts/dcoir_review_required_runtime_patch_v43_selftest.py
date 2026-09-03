#!/usr/bin/env python3
"""Offline regression checks for Architecture-B semantic-result reuse (v43)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v43 as v43
import dcoir_review_required_runtime_patch_v43_reuse as reuse


def fake_prompt(pr, item, file_text, diff, config, path_sentinels, review_mode):
    payload = {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "path": item.get("filename"),
        "blob": item.get("sha"),
        "text": file_text,
        "patch": item.get("patch"),
        "diff": diff,
        "minimum_confidence": config.minimum_confidence,
        "sentinels": sorted(getattr(value, "path", "") for value in path_sentinels),
        "review_mode": review_mode,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def risk_digest(sentinels):
    rows = sorted(
        (str(getattr(item, "path", "")), int(getattr(item, "line", 0) or 0))
        for item in sentinels
    )
    return reuse.sha_text(json.dumps(rows, separators=(",", ":")))


def make_module(semantic_calls, debug_payloads):
    module = SimpleNamespace()
    module.build_per_file_review_prompt = fake_prompt
    module.hardened = SimpleNamespace(
        risk_sentinel_digest=risk_digest,
        write_debug_json_artifact_safely=lambda _cfg, path, value: debug_payloads.__setitem__(path, value),
    )
    module.base = SimpleNamespace(sanitize_debug_json_value=lambda value, _cfg: value)

    def original_single(index, context, pr, diff, schema, config, risk_sentinels, review_mode):
        semantic_calls.append(str(context["path"]))
        prompt = module.build_per_file_review_prompt(
            pr,
            context["item"],
            context["text"],
            diff,
            config,
            [item for item in risk_sentinels if getattr(item, "path", None) == context["path"]],
            review_mode,
        )
        return {
            "path": context["path"],
            "prompt_chars": len(prompt),
            "result": {
                "summary": "same semantic result",
                "findings": [{"path": context["path"], "line": 2, "title": "same finding"}],
            },
            "model_used": "anthropic/claude-opus-5",
            "service_tier": "",
        }

    module.review_single_file_context = original_single

    def original_hybrid(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        item = files[0]
        context = {"item": item, "path": item["filename"], "text": "print('same')\n"}
        evidence = module.review_single_file_context(
            1, context, pr, diff, schema, config, risk_sentinels, review_mode
        )
        return evidence["result"], evidence["model_used"], evidence["service_tier"]

    module.openrouter_review_with_hybrid_first_pass = original_hybrid
    return module


def main() -> None:
    assert DcoirReviewEntrypoint().terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v41",
        "dcoir_review_required_runtime_patch_v42",
        "dcoir_review_required_runtime_patch_v43",
    )

    config = SimpleNamespace(
        model="anthropic/claude-opus-5",
        model_stack=["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"],
        minimum_confidence=0.70,
        per_file_first_pass_review=True,
        debug=False,
    )
    pr = {
        "number": 7,
        "title": "Reuse fixture",
        "base": {"sha": "0" * 40},
        "head": {"sha": "2" * 40},
    }
    files = [
        {
            "filename": "src/a.py",
            "status": "modified",
            "sha": "a" * 40,
            "patch": "@@ -1 +1,2 @@\n print('same')\n+print('old change')",
        },
        {"filename": "src/deleted.py", "status": "removed", "sha": ""},
    ]
    diff = "diff --git a/src/a.py b/src/a.py\n+print('old change')"
    schema = {"type": "object", "properties": {"findings": {"type": "array"}}}
    sentinels = [SimpleNamespace(path="src/a.py", line=2)]
    context = {"item": files[0], "path": "src/a.py", "text": "print('same')\n"}
    material_module = make_module([], {})
    material = reuse.reuse_material(
        material_module, context, pr, diff, schema, config, sentinels, "first-pass-deep"
    )
    reordered = reuse.reuse_material(
        material_module,
        {"text": context["text"], "path": context["path"], "item": dict(reversed(list(files[0].items())))},
        dict(reversed(list(pr.items()))),
        diff,
        dict(reversed(list(schema.items()))),
        config,
        list(reversed(sentinels)),
        "first-pass-deep",
    )
    assert material["reuse_key"] == reordered["reuse_key"]
    assert material["source_identity"] == f"blob:{'a' * 40}"
    assert material["dependency_context"]["contract"] == reuse.DEPENDENCY_CONTRACT
    assert material["dependency_context"]["mode"] == reuse.DEPENDENCY_MODE
    assert material["semantic_prompt_sha256"] == material["dependency_context"]["semantic_prompt_sha256"]

    prior_head = "1" * 40
    prior = {
        **material,
        "outcome": "complete",
        "result": {"summary": "same semantic result", "findings": []},
        "model_used": "anthropic/claude-opus-5",
        "service_tier": "",
        "origin_reviewed_head": prior_head,
        "carried_forward_head": prior_head,
    }
    assert reuse.evaluate_reuse_candidate(material, prior, prior_head) == (
        True,
        "exact-semantic-input-match",
    )

    cases = (
        (None, prior_head, "prior-record-missing"),
        ({**prior, "contract": "old"}, prior_head, "reuse-contract-mismatch"),
        ({**prior, "outcome": "partial"}, prior_head, "prior-result-incomplete"),
        (prior, "", "trusted-prior-head-missing"),
        ({**prior, "carried_forward_head": "9" * 40}, prior_head, "prior-head-mismatch"),
        ({**prior, "source_identity": "blob:" + "b" * 40}, prior_head, "source-changed"),
        ({**prior, "runtime_version": "v99"}, prior_head, "reviewer-runtime-changed"),
        ({**prior, "reviewer_fingerprint": "x" * 64}, prior_head, "reviewer-changed"),
        ({**prior, "schema_sha256": "x" * 64}, prior_head, "schema-changed"),
        ({**prior, "config_sha256": "x" * 64}, prior_head, "config-changed"),
        ({**prior, "dependency_sha256": "x" * 64}, prior_head, "dependency-context-changed"),
        ({**prior, "risk_fingerprint": "x" * 64}, prior_head, "risk-invariant-changed"),
        ({**prior, "review_mode": "diff"}, prior_head, "review-mode-changed"),
        ({**prior, "semantic_prompt_sha256": "x" * 64}, prior_head, "semantic-prompt-changed"),
        ({**prior, "reuse_key": "x" * 64}, prior_head, "reuse-key-mismatch"),
        ({**prior, "result": []}, prior_head, "prior-result-invalid"),
    )
    for candidate, head, expected_reason in cases:
        eligible, reason = reuse.evaluate_reuse_candidate(material, candidate, head)
        assert eligible is False
        assert reason == expected_reason

    manifest = {
        "contract": reuse.REUSE_CONTRACT,
        "outcome": "complete",
        "reviewed_head": prior_head,
        "records": [prior],
    }
    old_artifact_dir = os.environ.get(reuse.ARTIFACT_DIR_ENV)
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ[reuse.ARTIFACT_DIR_ENV] = temp_dir
            assert reuse.persist_manifest(material_module, config, manifest)
            stored = Path(temp_dir, reuse.MANIFEST_PATH)
            assert stored.is_file()
            assert json.loads(stored.read_text(encoding="utf-8"))["contract"] == reuse.REUSE_CONTRACT
    finally:
        if old_artifact_dir is None:
            os.environ.pop(reuse.ARTIFACT_DIR_ENV, None)
        else:
            os.environ[reuse.ARTIFACT_DIR_ENV] = old_artifact_dir

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"debug/{reuse.MANIFEST_PATH}", json.dumps(manifest))
    assert reuse.manifest_from_zip(archive_bytes.getvalue())["reviewed_head"] == prior_head
    old_max = reuse.MAX_ARTIFACT_BYTES
    try:
        reuse.MAX_ARTIFACT_BYTES = 16
        try:
            reuse.manifest_from_zip(archive_bytes.getvalue())
            raise AssertionError("oversized uncompressed manifest was accepted")
        except RuntimeError as exc:
            assert "exceeds read limit" in str(exc)
    finally:
        reuse.MAX_ARTIFACT_BYTES = old_max

    original_loader = reuse.trusted_prior_manifest
    original_last_context = v42_hooks._LAST_REVIEW_CONTEXT
    reporter_events = []
    reporter = SimpleNamespace(update=lambda stage, message: reporter_events.append((stage, message)))
    try:
        semantic_calls = []
        debug_payloads = {}
        reused_module = make_module(semantic_calls, debug_payloads)
        reused_material = reuse.reuse_material(
            reused_module, context, pr, diff, schema, config, sentinels, "first-pass-deep"
        )
        reused_record = {
            **reused_material,
            "outcome": "complete",
            "result": {
                "summary": "same semantic result",
                "findings": [{"path": "src/a.py", "line": 2, "title": "same finding"}],
            },
            "model_used": "anthropic/claude-opus-5",
            "service_tier": "",
            "origin_reviewed_head": prior_head,
            "carried_forward_head": prior_head,
        }
        reuse.trusted_prior_manifest = lambda _module, _gh, _pr: (
            {"records": [reused_record]},
            prior_head,
            "trusted-prior-manifest-loaded",
        )
        gh = SimpleNamespace()
        setattr(
            gh,
            v42_hooks.SEMANTIC_LEDGER_ATTR,
            {
                "review_surface": {
                    "files": [
                        {"path": "src/a.py", "status": "modified", "reuse_allowed": False},
                        {"path": "src/deleted.py", "status": "removed", "reuse_allowed": False},
                    ]
                },
                "telemetry": {},
                "reuse": {},
            },
        )
        v42_hooks._LAST_REVIEW_CONTEXT = None
        v43.apply_pareto_context_module(reused_module)
        with tempfile.TemporaryDirectory() as temp_dir:
            old_dir = os.environ.get(reuse.ARTIFACT_DIR_ENV)
            os.environ[reuse.ARTIFACT_DIR_ENV] = temp_dir
            try:
                reused_tuple = reused_module.openrouter_review_with_hybrid_first_pass(
                    pr,
                    files,
                    diff,
                    schema,
                    config,
                    reporter,
                    sentinels,
                    {},
                    "deep context",
                    "first-pass-deep",
                    "context summary",
                    gh,
                )
                assert Path(temp_dir, reuse.MANIFEST_PATH).is_file()
            finally:
                if old_dir is None:
                    os.environ.pop(reuse.ARTIFACT_DIR_ENV, None)
                else:
                    os.environ[reuse.ARTIFACT_DIR_ENV] = old_dir
        assert semantic_calls == []
        ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR)
        assert ledger["telemetry"]["reused_file_count"] == 1
        assert ledger["telemetry"]["recomputed_file_count"] == 0
        assert ledger["review_surface"]["files"][0]["reuse_allowed"] is True
        assert ledger["review_surface"]["files"][0]["reuse_decision"] == "reused"
        assert ledger["review_surface"]["files"][1]["reuse_reason"] == "deleted-file"
        assert any(item["decision"] == "not-applicable" for item in ledger["reuse_decisions"])

        recompute_calls = []
        recompute_debug = {}
        recompute_module = make_module(recompute_calls, recompute_debug)
        reuse.trusted_prior_manifest = lambda _module, _gh, _pr: (
            None,
            "",
            "trusted-prior-review-missing",
        )
        gh2 = SimpleNamespace()
        setattr(
            gh2,
            v42_hooks.SEMANTIC_LEDGER_ATTR,
            {
                "review_surface": {"files": [{"path": "src/a.py", "status": "modified"}]},
                "telemetry": {},
                "reuse": {},
            },
        )
        v43.apply_pareto_context_module(recompute_module)
        with tempfile.TemporaryDirectory() as temp_dir:
            old_dir = os.environ.get(reuse.ARTIFACT_DIR_ENV)
            os.environ[reuse.ARTIFACT_DIR_ENV] = temp_dir
            try:
                recomputed_tuple = recompute_module.openrouter_review_with_hybrid_first_pass(
                    pr,
                    files,
                    diff,
                    schema,
                    config,
                    reporter,
                    sentinels,
                    {},
                    "deep context",
                    "first-pass-deep",
                    "context summary",
                    gh2,
                )
            finally:
                if old_dir is None:
                    os.environ.pop(reuse.ARTIFACT_DIR_ENV, None)
                else:
                    os.environ[reuse.ARTIFACT_DIR_ENV] = old_dir
        assert recompute_calls == ["src/a.py"]
        assert recomputed_tuple == reused_tuple
        assert getattr(gh2, v42_hooks.SEMANTIC_LEDGER_ATTR)["telemetry"]["recomputed_file_count"] == 1
        assert any(stage == "semantic-reuse" for stage, _message in reporter_events)
    finally:
        reuse.trusted_prior_manifest = original_loader
        v42_hooks._LAST_REVIEW_CONTEXT = original_last_context

    source_root = Path(".github/dcoir_review/scripts")
    source = "\n".join(
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
        "trusted-prior-manifest-loaded",
        "persist_manifest",
        "semantic-reuse",
        "reuse_invalidation_reason",
    ):
        assert required in source
    for forbidden in ("openrouter.ai", "chat/completions", "git push", "merge_pull_request"):
        assert forbidden not in source

    print("dcoir_review_required_runtime_patch_v43_selftest passed")


if __name__ == "__main__":
    main()
