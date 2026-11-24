#!/usr/bin/env python3
"""Offline regression checks for repair critic candidate benchmark."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_repair_critic_candidate_eval as target


def main() -> None:
    cases = target.load_cases()
    assert [case["id"] for case in cases] == [
        "critic-complete-accept",
        "critic-partial-reject",
        "critic-unnecessary-extra-reject",
    ]
    assert target.score_response(True, True) == {"correct": True, "unsafe_accept": False}
    assert target.score_response(True, False) == {"correct": False, "unsafe_accept": False}
    assert target.score_response(False, False) == {"correct": True, "unsafe_accept": False}
    assert target.score_response(False, True) == {"correct": False, "unsafe_accept": True}

    plan = target.plan(
        [{"id": "a", "model": "vendor/a"}, {"id": "b", "model": "vendor/b"}],
        cases,
    )
    assert plan["case_counts"]["selected_cases"] == 3
    assert plan["case_counts"]["planned_total_requests"] == 6

    try:
        target.run_live([], [], timeout_seconds=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("nonpositive request timeout should fail before live execution")

    captured_configs = []

    def base_builder(_prompt, _schema, _config, _ignored, model):
        return {"model": model}

    def fake_openrouter_review(_prompt, _schema, config, reporter=None):
        captured_configs.append(config)
        return {"accepted": True, "confidence": 0.99, "reason": "accepted"}, "vendor/a", ""

    review = SimpleNamespace(
        hardened=SimpleNamespace(
            build_openrouter_payload=base_builder,
            openrouter_review=fake_openrouter_review,
        ),
        base=SimpleNamespace(sanitize_text=lambda text, _config: str(text)),
    )
    v21 = SimpleNamespace(VERIFIER_MARKER="_verifier")
    original_candidate_config = target._candidate_config
    target._candidate_config = lambda _review, _candidate: SimpleNamespace(
        model="vendor/a",
        model_stack=["vendor/a"],
        fallback_models=[],
        openrouter_route="",
        openrouter_service_tier="",
        openrouter_session_id_prefix="benchmark",
    )
    try:
        target._run_case(
            review,
            v21,
            {"id": "a", "model": "vendor/a"},
            cases[0],
            timeout_seconds=37,
        )
    finally:
        target._candidate_config = original_candidate_config
    assert captured_configs[0].openrouter_request_timeout_seconds == 37

    def base_builder(_prompt, _schema, _config, _ignored, model):
        return {"model": model, "temperature": 0.2}

    no_temp = target.repair_eval._candidate_payload_builder(
        base_builder,
        {"id": "astra", "model": "openai/gpt-6-astra", "temperature": None},
    )
    assert "temperature" not in no_temp("", {}, None, [], "openai/gpt-6-astra")

    complete = cases[0]["author"]["edits"]
    partial = cases[1]["author"]["edits"]
    extra = cases[2]["author"]["edits"]
    assert len(complete) == 2
    assert len(partial) == 1
    assert len(extra) == 3
    assert extra[-1]["start_line"] == 2

    print("dcoir_review_repair_critic_candidate_eval_selftest passed")


if __name__ == "__main__":
    main()
