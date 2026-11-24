#!/usr/bin/env python3
"""Offline regressions for canonical semantic context and adaptive budgets."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

from dcoir_review import incremental_review_scope as v41_scope
from dcoir_review import semantic_context
from dcoir_review import adaptive_semantic_budget as budget
from dcoir_review import semantic_context_runtime as context
from dcoir_review import semantic_context_contract as contract
from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review import review_config


ROOT = Path(__file__).resolve().parent.parent
HEAD = "b" * 40
PR = {"number": 474, "title": "semantic context", "head": {"sha": HEAD}}
FILES = [
    {
        "filename": "src/a.py",
        "status": "modified",
        "sha": "a" * 40,
        "patch": "@@ -1 +1 @@\n-old\n+new",
    }
]


class ReviewQualityError(RuntimeError):
    pass


def config(**overrides):
    values = {
        "canonical_semantic_context_review": True,
        "adaptive_semantic_budgets_review": True,
        "max_prompt_chars": 120000,
        "deep_review_max_total_chars": 60000,
        "candidate_escalation_total_context_chars": 48000,
        "semantic_adjudication_candidate_digest_chars": 24000,
        "max_inline_comments": 12,
        "adaptive_semantic_min_prompt_chars": 48000,
        "adaptive_semantic_small_delta_prompt_chars": 60000,
        "adaptive_semantic_small_delta_max_files": 4,
        "adaptive_semantic_small_delta_max_diff_chars": 20000,
        "adaptive_semantic_small_delta_max_context_chars": 30000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def hardened(artifacts=None):
    sink = artifacts if artifacts is not None else {}
    return SimpleNamespace(
        ReviewQualityError=ReviewQualityError,
        risk_sentinel_digest=lambda values: f"risk:{len(values)}",
        write_debug_json_artifact_safely=lambda _cfg, name, value: sink.__setitem__(
            name, copy.deepcopy(value)
        ),
        parse_yaml_like_data=lambda _path: {},
        bool_value=lambda data, key, default: data.get(key, default),
    )


def package_metadata(**overrides):
    values = {
        "package_id": "package",
        "review_mode": "diff",
        "scope_source": "incremental-reviewed-head",
        "scope_compare_status": "ahead",
        "scope_fallback_reason": "",
        "risk_sentinel_count": 0,
        "changed_file_count": 1,
        "diff_chars": 1000,
        "deep_context_chars": 500,
    }
    values.update(overrides)
    return {"metadata": values}


def test_context_package_is_deterministic_and_exact_head() -> None:
    module = SimpleNamespace(hardened=hardened())
    gh = SimpleNamespace(
        **{
            v41_scope.SCOPE_CACHE_ATTR: {
                "source": "incremental-reviewed-head",
                "compare_status": "ahead",
                "fallback_reason": "",
            }
        }
    )
    calls = []

    def build_contexts(_gh, _pr, _files, _config):
        calls.append(True)
        return [
            {"path": "src/z.py", "text": "z", "sha": "c" * 40},
            {"path": "src/a.py", "text": "a", "sha": "d" * 40},
        ]

    args = (
        module,
        gh,
        PR,
        FILES,
        "diff",
        {"type": "object"},
        config(),
        [],
        "deep",
        "first-pass-deep",
        "summary",
        build_contexts,
    )
    first = context.build_context_runtime(*args)
    second = context.build_context_runtime(*args)
    assert first["metadata"] == second["metadata"]
    assert first["metadata"]["reviewed_head"] == HEAD
    assert [row["path"] for row in first["metadata"]["file_context_records"]] == [
        "src/a.py",
        "src/z.py",
    ]
    assert first["telemetry"]["file_context_fetch_pass_count"] == 1
    assert len(calls) == 2
    assert "file_contexts" not in context.public_payload(first)

    bad_pr = {**PR, "head": {"sha": "short"}}
    bad_args = list(args)
    bad_args[2] = bad_pr
    try:
        context.build_context_runtime(*bad_args)
    except ReviewQualityError as exc:
        assert "exact 40-character" in str(exc)
    else:
        raise AssertionError("missing exact head must fail closed")


def test_adaptive_budget_is_narrow_and_fail_safe() -> None:
    small = budget.select_budget_plan(package_metadata(), config(), [])
    assert small["mode"] == "small-incremental-delta"
    assert small["selected"]["max_prompt_chars"] == 60000
    assert small["selected"]["deep_review_max_total_chars"] == 30000
    assert small["selected"]["candidate_escalation_total_context_chars"] == 48000
    assert small["selected"]["max_inline_comments"] == 12
    assert small["quality_floor_preserved"] is True

    cases = (
        ({"review_mode": "first-pass-deep"}, [], "initial-or-deep"),
        ({"scope_source": "full-pr"}, [], "non-incremental"),
        ({"scope_compare_status": "diverged"}, [], "untrusted"),
        ({"scope_fallback_reason": "compare-failed"}, [], "scope-fallback"),
        ({"changed_file_count": 5}, [], "changed-file-count"),
        ({"diff_chars": 20001}, [], "diff-size"),
        ({"deep_context_chars": 30001}, [], "dependency-context-size"),
        ({}, ["risky"], "risk-sentinel"),
    )
    for changes, sentinels, reason in cases:
        plan = budget.select_budget_plan(package_metadata(**changes), config(), sentinels)
        assert plan["mode"] == "full-quality-floor"
        assert plan["selected"]["max_prompt_chars"] == 120000
        assert reason in plan["reasons"][0]

    disabled = budget.select_budget_plan(
        package_metadata(), config(adaptive_semantic_budgets_review=False), []
    )
    assert disabled["mode"] == "full-quality-floor"
    assert disabled["reasons"] == ["adaptive-budgets-disabled"]


def make_review_module():
    artifacts = {}
    calls = {"contexts": 0, "file_prompt": 0, "broad_prompt": 0, "hybrid": 0}
    module = SimpleNamespace(hardened=hardened(artifacts))
    module.load_pareto_context_config = lambda _path: config()

    def build_contexts(_gh, _pr, _files, _config):
        calls["contexts"] += 1
        return [{"path": "src/a.py", "text": "source", "sha": "a" * 40}]

    def file_prompt(_pr, item, file_text, diff, _cfg, _risks, mode):
        calls["file_prompt"] += 1
        return f"file:{item['filename']}:{file_text}:{diff}:{mode}"

    def broad_prompt(_pr, _files, diff, _cfg, _risks, deep, mode, summary):
        calls["broad_prompt"] += 1
        return f"broad:{diff}:{deep}:{mode}:{summary}"

    module.build_file_contexts = build_contexts
    module.build_per_file_review_prompt = file_prompt
    module.build_prompt = broad_prompt

    def hybrid(
        pr,
        files,
        diff,
        _schema,
        cfg,
        _reporter,
        risks,
        _index,
        deep,
        mode,
        summary,
        gh,
    ):
        calls["hybrid"] += 1
        contexts = module.build_file_contexts(gh, pr, files, cfg)
        first = module.build_per_file_review_prompt(
            pr, files[0], contexts[0]["text"], diff, cfg, risks, mode
        )
        second = module.build_per_file_review_prompt(
            pr, files[0], contexts[0]["text"], diff, cfg, risks, mode
        )
        broad_first = module.build_prompt(
            pr, files, diff, cfg, risks, deep, mode, summary
        )
        broad_second = module.build_prompt(
            pr, files, diff, cfg, risks, deep, mode, summary
        )
        assert first == second and broad_first == broad_second
        return {"summary": "ok", "findings": []}, "model", "tier"

    module.openrouter_review_with_hybrid_first_pass = hybrid
    return module, artifacts, calls


def invoke(module, cfg=None, *, diff="diff", mode="first-pass-deep", gh=None):
    target = gh or SimpleNamespace()
    setattr(
        target,
        v41_scope.SCOPE_CACHE_ATTR,
        {
            "source": "incremental-reviewed-head",
            "compare_status": "ahead",
            "fallback_reason": "",
        },
    )
    reporter = SimpleNamespace(events=[])
    reporter.update = lambda key, value: reporter.events.append((key, value))
    result = module.openrouter_review_with_hybrid_first_pass(
        PR,
        FILES,
        diff,
        {"type": "object"},
        cfg or config(),
        reporter,
        [],
        {},
        "deep",
        mode,
        "summary",
        target,
    )
    return result, target, reporter


def apply_semantic_context_with_hybrid_stage(module) -> None:
    base_hybrid = module.openrouter_review_with_hybrid_first_pass
    builder = semantic_context.install(module)
    module.openrouter_review_with_hybrid_first_pass = builder(module, base_hybrid)


def test_composed_context_reuse_and_artifacts() -> None:
    module, artifacts, calls = make_review_module()
    apply_semantic_context_with_hybrid_stage(module)
    (result, model, tier), gh, reporter = invoke(module)
    assert result["_semantic_context_package_id"]
    assert result["_adaptive_semantic_budget_mode"] == "full-quality-floor"
    assert (model, tier) == ("model", "tier")
    assert calls == {"contexts": 1, "file_prompt": 1, "broad_prompt": 1, "hybrid": 1}
    package = module.semantic_context_package_for_client(gh)
    telemetry = package["telemetry"]
    assert telemetry["file_context_projection_reuse_count"] == 1
    assert telemetry["per_file_prompt_build_count"] == 1
    assert telemetry["per_file_prompt_reuse_count"] == 1
    assert telemetry["broad_prompt_build_count"] == 1
    assert telemetry["broad_prompt_reuse_count"] == 1
    assert "file_contexts" not in package
    assert package["outcome"] == "completed"
    assert reporter.events[0][0] == "semantic-context-budget"
    assert "metadata/semantic-context-package-v46.json" in artifacts
    assert "metadata/adaptive-semantic-budget-v46.json" in artifacts

    before = calls["broad_prompt"]
    active_config = config()
    setattr(active_config, contract.CONFIG_PACKAGE_ID_ATTR, package["package_id"])
    module.build_prompt(
        PR,
        FILES,
        "different",
        active_config,
        [],
        "deep",
        "first-pass-deep",
        "summary",
    )
    assert calls["broad_prompt"] == before + 1
    runtime = getattr(module, contract.RUNTIME_ATTR)
    assert runtime["telemetry"]["fallback_projection_count"] == 1


def test_incremental_budget_and_rollback() -> None:
    module, _artifacts, calls = make_review_module()
    apply_semantic_context_with_hybrid_stage(module)
    gh = invoke(module, diff="tiny", mode="diff", cfg=config(), gh=SimpleNamespace())[1]
    package = module.semantic_context_package_for_client(gh)
    assert package["budget_plan"]["mode"] == "small-incremental-delta"
    assert package["budget_plan"]["selected"]["max_prompt_chars"] == 60000

    rollback, _rollback_artifacts, rollback_calls = make_review_module()
    apply_semantic_context_with_hybrid_stage(rollback)
    invoke(rollback, cfg=config(canonical_semantic_context_review=False))
    assert rollback_calls["hybrid"] == 1
    assert not hasattr(rollback, contract.RUNTIME_ATTR)
    assert calls["hybrid"] == 1


def test_installation_boundary_is_fail_closed() -> None:
    broken = SimpleNamespace(
        build_file_contexts=lambda *_args, **_kwargs: [],
        build_per_file_review_prompt=None,
        build_prompt=lambda *_args, **_kwargs: "prompt",
    )
    original_contexts = broken.build_file_contexts
    original_prompt = broken.build_prompt
    try:
        semantic_context.install(broken)
    except RuntimeError as exc:
        assert "could not locate semantic context builders" in str(exc)
    else:
        raise AssertionError("missing semantic-context builder must fail closed")
    assert broken.build_file_contexts is original_contexts
    assert broken.build_per_file_review_prompt is None
    assert broken.build_prompt is original_prompt

    module, _artifacts, _calls = make_review_module()
    base_hybrid = module.openrouter_review_with_hybrid_first_pass
    builder = semantic_context.install(module)
    try:
        builder(SimpleNamespace(), base_hybrid)
    except RuntimeError as exc:
        assert "wrong review module" in str(exc)
    else:
        raise AssertionError("semantic-context builder must remain bound to its review module")


def test_stable_budget_projection_attributes() -> None:
    package = package_metadata()
    plan = budget.select_budget_plan(package, config(), [])
    staged = budget.configured_for_plan(config(), plan)
    assert getattr(staged, contract.CONFIG_PACKAGE_ID_ATTR) == plan["package_id"]
    assert getattr(staged, contract.BUDGET_MODE_ATTR) == plan["mode"]
    assert not hasattr(staged, "_dcoir_v46_context_package_id")
    assert not hasattr(staged, "_dcoir_v46_budget_mode")


def test_config_and_production_registration() -> None:
    module, _artifacts, _calls = make_review_module()
    loaded = module.load_pareto_context_config("unused.yml")
    review_config.apply_review_config(loaded, module.hardened.parse_yaml_like_data("unused.yml"), module.hardened)
    assert loaded.canonical_semantic_context_review is True
    assert loaded.adaptive_semantic_budgets_review is True
    assert loaded.adaptive_semantic_small_delta_prompt_chars == 60000

    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names == (
        "dcoir_review.publication_disposition",
        "dcoir_review.verified_finding_gate",
    )
    assert "canonical-semantic-context" in entrypoint.import_module(
        "dcoir_review.review_orchestration"
    ).STAGE_ORDER
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "canonical_semantic_context_review: true" in production
    assert "adaptive_semantic_budgets_review: true" in production
    assert "dcoir_review_semantic_context_selftest.py" in production
    review = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(review)
    production_config = review.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )
    assert production_config.canonical_semantic_context_review is True
    assert production_config.adaptive_semantic_budgets_review is True
    assert callable(getattr(review, "semantic_context_package_for_client", None))
    for name in (
        "_dcoir_v46_original_build_file_contexts",
        "_dcoir_v46_original_build_per_file_review_prompt",
        "_dcoir_v46_original_build_prompt",
    ):
        assert not hasattr(review, name), name


def main() -> None:
    test_context_package_is_deterministic_and_exact_head()
    test_adaptive_budget_is_narrow_and_fail_safe()
    test_composed_context_reuse_and_artifacts()
    test_incremental_budget_and_rollback()
    test_installation_boundary_is_fail_closed()
    test_stable_budget_projection_attributes()
    test_config_and_production_registration()
    print("dcoir_review_semantic_context_selftest passed")


if __name__ == "__main__":
    main()
