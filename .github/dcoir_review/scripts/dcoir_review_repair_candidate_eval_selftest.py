#!/usr/bin/env python3
"""Offline regression checks for the DCOIR repair candidate benchmark."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_repair_candidate_eval as repair_eval


def _marker_from_expected(case):
    return {
        "outcome": "verified-repair-set",
        "critic_accepted": True,
        "author_model": "vendor/a",
        "critic_model": "vendor/b",
        "edits": [
            {
                "path": edit["path"],
                "start_line": edit["start_line"],
                "end_line": edit["end_line"],
                "replacement": edit["replacement"],
            }
            for edit in case["expected_edits"]
        ],
    }


def main() -> None:
    cases = repair_eval.load_cases()
    assert [case["id"] for case in cases] == [
        "repair-upper-bound-one-line",
        "repair-coordinated-two-edit",
        "repair-pr581-urlopen-false-positive",
    ]

    selected = repair_eval.select_cases(["repair-coordinated-two-edit"])
    assert len(selected) == 1
    assert len(selected[0]["expected_edits"]) == 2

    plan = repair_eval.plan(
        [{"id": "a", "model": "vendor/a"}, {"id": "b", "model": "vendor/b"}],
        selected,
    )
    # Worst case per case: one author call plus every critic fallback. A
    # non-OpenAI author gets the two-model OpenAI critic stack.
    assert plan["case_counts"]["planned_total_requests"] == 6
    openai_plan = repair_eval.plan([{"id": "c", "model": "openai/gpt-6-astra"}], selected)
    # An OpenAI author gets the three-model Anthropic/Google critic stack.
    assert openai_plan["case_counts"]["planned_total_requests"] == 4

    try:
        repair_eval.run_live([], [], timeout_seconds=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("nonpositive request timeout should fail before live execution")

    captured_configs = []

    def fake_build_repair_set(*args, author_config_override=None):
        captured_configs.append(author_config_override)
        return {}

    production_config = SimpleNamespace(
        model="anthropic/claude-opus-5.5",
        model_stack=["anthropic/claude-opus-5.5"],
        review_reasoning_effort="xhigh",
        openrouter_max_attempts=4,
    )
    review = SimpleNamespace(
        load_pareto_context_config=lambda _path: production_config,
        fetch_pr_file_text=None,
        hardened=SimpleNamespace(
            write_debug_json_artifact_safely=None,
            build_openrouter_payload=lambda *_args: {},
        ),
        base=SimpleNamespace(build_diff_line_index=lambda _diff: {}),
    )
    fake_v36 = SimpleNamespace(REPAIR_SET_OUTCOME="verified-repair-set")
    original_builder = repair_eval.repair_set_builder.build_repair_set_for_finding
    repair_eval.repair_set_builder.build_repair_set_for_finding = fake_build_repair_set
    try:
        repair_eval._run_case(
            review,
            SimpleNamespace(VERIFIER_MARKER="_verifier"),
            SimpleNamespace(REPAIR_MARKER="_repair"),
            fake_v36,
            {"id": "kimi", "model": "moonshotai/kimi-k3", "reasoning_effort": None},
            selected[0],
            timeout_seconds=37,
        )
    finally:
        repair_eval.repair_set_builder.build_repair_set_for_finding = original_builder
    author_config = captured_configs[0]
    assert author_config.model_stack == ["moonshotai/kimi-k3"]
    assert author_config.openrouter_request_timeout_seconds == 37
    assert author_config.openrouter_max_attempts == 1
    # The candidate's reasoning shape is applied per request, not by mutating
    # the shared effort that critic fallbacks inherit.
    assert author_config.review_reasoning_effort == "xhigh"
    assert production_config.openrouter_max_attempts == 4

    def base_builder(_prompt, _schema, _config, _ignored, model):
        return {
            "model": model,
            "temperature": 0.2,
            "reasoning": {"enabled": True, "effort": "xhigh", "exclude": True},
        }

    no_reasoning = repair_eval._candidate_payload_builder(
        base_builder,
        {"id": "kimi", "model": "moonshotai/kimi-k3", "reasoning_effort": None},
    )
    assert "reasoning" not in no_reasoning("", {}, None, [], "moonshotai/kimi-k3")
    assert no_reasoning("", {}, None, [], "openai/gpt-5.6-sol-pro")["reasoning"]["effort"] == "xhigh"
    high_reasoning = repair_eval._candidate_payload_builder(
        base_builder,
        {"id": "sonnet", "model": "anthropic/claude-sonnet-5.5", "reasoning_effort": "high"},
    )
    assert high_reasoning("", {}, None, [], "anthropic/claude-sonnet-5.5")["reasoning"] == {
        "enabled": True,
        "effort": "high",
        "exclude": True,
    }

    no_temp = repair_eval._candidate_payload_builder(
        base_builder,
        {"id": "astra", "model": "openai/gpt-6-astra", "temperature": None},
    )
    author_payload = no_temp("", {}, None, [], "openai/gpt-6-astra")
    critic_payload = no_temp("", {}, None, [], "anthropic/claude-opus-5")
    assert "temperature" not in author_payload
    assert critic_payload["temperature"] == 0.2

    explicit_temp = repair_eval._candidate_payload_builder(
        base_builder,
        {"id": "prod", "model": "openai/gpt-6-astra", "temperature": 0.7},
    )
    assert explicit_temp("", {}, None, [], "openai/gpt-6-astra")["temperature"] == 0.7

    repair = SimpleNamespace(REPAIR_MARKER="_repair")
    v36 = SimpleNamespace(REPAIR_SET_OUTCOME="verified-repair-set")

    for case in cases[:2]:
        item = {"_repair": _marker_from_expected(case)}
        score = repair_eval.score_item(item, case, repair, v36)
        assert score["correct"] is True and score["unsafe_accept"] is False

        partial_edits = list(item["_repair"]["edits"][:-1])
        bad = {"_repair": dict(item["_repair"], edits=partial_edits)}
        score = repair_eval.score_item(bad, case, repair, v36)
        assert score["correct"] is False and score["unsafe_accept"] is True

    historical = cases[2]
    suppressed = {"_repair": {"outcome": "defect-absent-suppressed", "edits": []}}
    score = repair_eval.score_item(suppressed, historical, repair, v36)
    assert score["correct"] is True and score["unsafe_accept"] is False

    bad_patch = {"_repair": {"outcome": "verified-repair-set", "critic_accepted": True, "edits": [
        {"path": historical["path"], "start_line": historical["line"], "end_line": historical["line"], "replacement": "pass"}
    ]}}
    score = repair_eval.score_item(bad_patch, historical, repair, v36)
    assert score["correct"] is False and score["unsafe_accept"] is True

    print("dcoir_review_repair_candidate_eval_selftest passed")


if __name__ == "__main__":
    main()
