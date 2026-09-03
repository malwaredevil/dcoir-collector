#!/usr/bin/env python3
"""Offline end-to-end regressions for Architecture-B escalation v44."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v44 as v44


FILES = [
    {"filename": "src/a.py", "status": "modified"},
    {"filename": "src/b.py", "status": "modified"},
    {"filename": "src/c.py", "status": "modified"},
]
PR = {"number": 470, "title": "v44", "head": {"sha": "4" * 40}}


def finding(path: str, title: str) -> dict[str, object]:
    return {
        "path": path,
        "line": 4,
        "severity": "medium",
        "confidence": 0.75,
        "title": title,
        "body": "Exact changed-line evidence.",
    }


def config():
    return SimpleNamespace(
        candidate_scoped_escalation_review=True,
        adversarial_confirmation_review=True,
        semantic_adjudication_review=True,
    )


def make_module(primary_findings):
    original_calls = []
    debug = {}
    module = SimpleNamespace()

    def original(
        _pr,
        _files,
        _diff,
        _schema,
        cfg,
        _reporter,
        _sentinels,
        _index,
        _deep,
        _mode,
        _summary,
        _gh,
    ):
        original_calls.append(
            (
                bool(cfg.adversarial_confirmation_review),
                bool(cfg.semantic_adjudication_review),
            )
        )
        return {"summary": "primary", "findings": list(primary_findings)}, "primary", "p"

    module.openrouter_review_with_hybrid_first_pass = original
    module.hardened = SimpleNamespace(
        result_findings=lambda result: result.get("findings", []),
        write_debug_json_artifact_safely=lambda _cfg, name, value: debug.__setitem__(
            name, value
        ),
        ReviewQualityError=RuntimeError,
    )
    v44._patch_semantic_escalation(module)
    return module, original_calls, debug


def invoke(module, cfg=None, mode="first-pass-deep", gh=None):
    return module.openrouter_review_with_hybrid_first_pass(
        PR,
        FILES,
        "full diff",
        {"type": "object"},
        cfg or config(),
        None,
        [],
        {},
        "deep context",
        mode,
        "context summary",
        gh or SimpleNamespace(),
    )


def patch_execution(
    plan, challenger_results, adjudicated_findings, adjudicated_results=None
):
    originals = (
        v44.scope.build_escalation_plan,
        v44.scope.build_bounded_evidence,
        v44.execution.broad_evidence,
        v44.execution.run_challenger,
        v44.execution.run_adjudicator,
    )
    calls = {"challenger": [], "adjudicator": []}
    queue = list(challenger_results)
    adjudicator_queue = list(adjudicated_results or [adjudicated_findings])
    v44.scope.build_escalation_plan = lambda *_args: dict(plan)
    v44.scope.build_bounded_evidence = lambda *_args: ("BOUNDED", "")
    v44.execution.broad_evidence = lambda *_args: "BROAD"

    def challenger(_module, _schema, _config, _reporter, evidence, context_scope):
        calls["challenger"].append((evidence, context_scope))
        return queue.pop(0), f"challenger-{context_scope}", "c"

    def adjudicator(
        _module,
        _schema,
        _config,
        _reporter,
        hypotheses,
        evidence,
        context_scope,
    ):
        calls["adjudicator"].append((hypotheses, evidence, context_scope))
        findings = adjudicator_queue.pop(0)
        return (
            {
                "summary": "adjudicated",
                "findings": list(findings),
                "_semantic_adjudication_model": "adjudicator",
                "_semantic_adjudication_input_candidates": len(hypotheses),
            },
            "adjudicator",
            "a",
        )

    v44.execution.run_challenger = challenger
    v44.execution.run_adjudicator = adjudicator
    return originals, calls


def restore_execution(originals) -> None:
    (
        v44.scope.build_escalation_plan,
        v44.scope.build_bounded_evidence,
        v44.execution.broad_evidence,
        v44.execution.run_challenger,
        v44.execution.run_adjudicator,
    ) = originals


def test_no_escalation() -> None:
    primary = [finding("src/c.py", "pass through")]
    module, original_calls, debug = make_module(primary)
    originals, calls = patch_execution(
        {
            "mode": "none",
            "reasons": ["confident-low-risk-primary-evidence"],
            "candidate_count": 1,
            "selected_paths": [],
            "escalated_candidate_keys": [],
        },
        [],
        [],
    )
    try:
        result, model, tier = invoke(module)
    finally:
        restore_execution(originals)
    assert result["findings"] == primary
    assert model == "primary" and tier == "p"
    assert calls == {"challenger": [], "adjudicator": []}
    assert original_calls == [(False, False)]
    assert result["_candidate_escalation"]["context_scope"] == "primary-only"
    assert debug["metadata/v44-candidate-escalation.json"]["widened"] is False


def test_candidate_scope_preserves_passthrough_and_telemetry() -> None:
    scoped = finding("src/a.py", "scoped")
    passthrough = finding("src/c.py", "pass through")
    challenged = finding("src/a.py", "challenger")
    retained = finding("src/a.py", "retained")
    module, _original_calls, debug = make_module([scoped, passthrough])
    gh = SimpleNamespace()
    setattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, {"telemetry": {}})
    originals, calls = patch_execution(
        {
            "mode": "candidate-scoped",
            "reasons": ["near-publication-threshold"],
            "candidate_count": 2,
            "selected_paths": ["src/a.py"],
            "escalated_candidate_keys": [["src/a.py", 4, "scoped"]],
        },
        [{"findings": [challenged]}],
        [retained],
    )
    old_context = v42_hooks._LAST_REVIEW_CONTEXT
    v42_hooks._LAST_REVIEW_CONTEXT = None
    try:
        result, _model, _tier = invoke(module, gh=gh)
    finally:
        v42_hooks._LAST_REVIEW_CONTEXT = old_context
        restore_execution(originals)
    assert result["findings"] == [passthrough, retained]
    assert calls["challenger"] == [("BOUNDED", "candidate-scoped")]
    hypotheses, evidence, context_scope = calls["adjudicator"][0]
    assert hypotheses == [scoped, challenged]
    assert evidence == "BOUNDED" and context_scope == "candidate-scoped"
    metadata = result["_candidate_escalation"]
    assert metadata["challenger_call_count"] == 1
    assert metadata["adjudicator_call_count"] == 1
    assert metadata["widened"] is False
    assert metadata["candidate_decisions"][0] == {
        "key": ["src/a.py", 4, "scoped"],
        "mode": "candidate-scoped",
        "reasons": ["near-publication-threshold"],
    }
    ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR)
    assert ledger["telemetry"]["escalated_candidate_count"] == 1
    assert debug["metadata/v44-candidate-escalation.json"] == metadata


def test_outside_challenger_finding_widens_and_reruns() -> None:
    primary = finding("src/a.py", "primary")
    escaped = finding("src/b.py", "unscoped first answer")
    broad = finding("src/b.py", "broadly confirmed")
    module, _original_calls, _debug = make_module([primary])
    originals, calls = patch_execution(
        {
            "mode": "candidate-scoped",
            "reasons": ["near-publication-threshold"],
            "candidate_count": 1,
            "selected_paths": ["src/a.py"],
            "escalated_candidate_keys": [["src/a.py", 4, "primary"]],
        },
        [{"findings": [escaped]}, {"findings": [broad]}],
        [broad],
    )
    try:
        result, model, _tier = invoke(module)
    finally:
        restore_execution(originals)
    assert calls["challenger"] == [
        ("BOUNDED", "candidate-scoped"),
        ("BROAD", "broader-context"),
    ]
    hypotheses, evidence, context_scope = calls["adjudicator"][0]
    assert hypotheses == [primary, broad]
    assert escaped not in hypotheses
    assert evidence == "BROAD" and context_scope == "broader-context"
    metadata = result["_candidate_escalation"]
    assert metadata["mode"] == "broader-context"
    assert "challenger-outside-bounded-scope" in metadata["reasons"]
    assert metadata["challenger_call_count"] == 2
    assert metadata["adjudicator_call_count"] == 1
    assert metadata["widened"] is True
    assert metadata["selected_paths"] == ["src/a.py", "src/b.py", "src/c.py"]
    assert all(
        item["mode"] == "broader-context"
        for item in metadata["candidate_decisions"]
    )
    assert "challenger-broader-context" in model


def test_outside_adjudicator_finding_widens_and_reruns() -> None:
    primary = finding("src/a.py", "primary")
    escaped = finding("src/b.py", "unscoped adjudication")
    broad = finding("src/b.py", "broadly adjudicated")
    module, _original_calls, _debug = make_module([primary])
    originals, calls = patch_execution(
        {
            "mode": "candidate-scoped",
            "reasons": ["near-publication-threshold"],
            "candidate_count": 1,
            "selected_paths": ["src/a.py"],
            "escalated_candidate_keys": [["src/a.py", 4, "primary"]],
        },
        [{"findings": [finding("src/a.py", "challenger")]}, {"findings": [broad]}],
        [escaped],
        adjudicated_results=[[escaped], [broad]],
    )
    try:
        result, _model, _tier = invoke(module)
    finally:
        restore_execution(originals)
    assert calls["challenger"] == [
        ("BOUNDED", "candidate-scoped"),
        ("BROAD", "broader-context"),
    ]
    assert len(calls["adjudicator"]) == 2
    assert calls["adjudicator"][0][2] == "candidate-scoped"
    assert calls["adjudicator"][1][1:] == ("BROAD", "broader-context")
    metadata = result["_candidate_escalation"]
    assert metadata["mode"] == "broader-context"
    assert "adjudicator-outside-bounded-scope" in metadata["reasons"]
    assert metadata["challenger_call_count"] == 2
    assert metadata["adjudicator_call_count"] == 2
    assert metadata["widened"] is True
    assert result["findings"] == [primary, finding("src/b.py", "broadly adjudicated")]


def test_disabled_escalation_stages_delegate_to_original() -> None:
    module, original_calls, _debug = make_module([finding("src/a.py", "primary")])
    cfg = config()
    cfg.adversarial_confirmation_review = False
    result, model, tier = invoke(module, cfg=cfg)
    assert result["summary"] == "primary"
    assert model == "primary" and tier == "p"
    assert original_calls == [(False, True)]


def test_explicit_deep_delegates_to_existing_broad_contract() -> None:
    module, original_calls, _debug = make_module([finding("src/a.py", "primary")])
    result, model, tier = invoke(module, mode="deep-forced")
    assert result["summary"] == "primary"
    assert model == "primary" and tier == "p"
    metadata = result["_candidate_escalation"]
    assert metadata["mode"] == "full-deep"
    assert metadata["context_scope"] == "full-deep"
    assert metadata["explicit_deep_forced"] is True
    assert metadata["reasons"] == ["explicit-deep-mode"]
    assert metadata["challenger_call_count"] == 1
    assert metadata["adjudicator_call_count"] == 1
    assert original_calls == [(True, True)]


def test_flat_shape_recovery_stays_inside_bounded_adjudication() -> None:
    calls = []
    debug = {}
    flat = {
        "title": "Recovered flat finding",
        "severity": "medium",
        "confidence": 0.82,
        "path": "src/a.py",
        "line": 4,
        "body": "The exact changed line demonstrates the defect.",
        "validation": "python3 -m py_compile src/a.py",
    }
    module = SimpleNamespace(
        base=SimpleNamespace(sanitize_text=lambda value, _cfg: str(value)),
        hardened=SimpleNamespace(
            openrouter_review=lambda *_args: (
                calls.append("bounded-adjudicator") or dict(flat),
                "adjudicator",
                "",
            ),
            result_findings=lambda result: result.get("findings", []),
            write_debug_text_artifact_safely=lambda _cfg, name, value: debug.__setitem__(
                name, value
            ),
            write_debug_json_artifact_safely=lambda _cfg, name, value: debug.__setitem__(
                name, value
            ),
            ReviewQualityError=RuntimeError,
        ),
    )
    cfg = SimpleNamespace(
        semantic_adjudication_model_stack=["adjudicator"],
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        max_prompt_chars=120000,
        minimum_confidence=0.70,
    )
    result, model, tier = v44.execution.run_adjudicator(
        module,
        {"type": "object"},
        cfg,
        None,
        [flat],
        "BOUNDED",
        "candidate-scoped",
    )
    assert calls == ["bounded-adjudicator"]
    assert result["findings"] == [flat]
    assert result["_semantic_adjudication_result_shape"] == "flat-single-finding"
    assert result["_semantic_adjudication_context_scope"] == "candidate-scoped"
    assert model == "adjudicator" and tier == ""
    assert "BROAD" not in debug["prompts/09-v44-candidate-adjudication.txt"]


def main() -> None:
    assert v44._challenger_outside_scope(
        SimpleNamespace(
            hardened=SimpleNamespace(result_findings=lambda result: result["findings"])
        ),
        {"findings": [{"path": ""}]},
        {"src/a.py"},
    )
    test_no_escalation()
    test_candidate_scope_preserves_passthrough_and_telemetry()
    test_outside_challenger_finding_widens_and_reruns()
    test_explicit_deep_delegates_to_existing_broad_contract()
    test_flat_shape_recovery_stays_inside_bounded_adjudication()
    print("dcoir_review_required_runtime_patch_v44_selftest passed")


if __name__ == "__main__":
    main()
