#!/usr/bin/env python3
"""Deterministic regression checks for issue #524 adjudicator-shape recovery."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v37 as v37
import dcoir_review_required_runtime_patch_v44_execution as execution


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


class Hardened:
    ReviewQualityError = RuntimeError

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.calls = 0
        self.artifacts: dict[str, Any] = {}

    def openrouter_review(self, _prompt, _schema, _config, _reporter=None):
        self.calls += 1
        return self.raw, "adjudicator-model", "default"

    @staticmethod
    def result_findings(result: Any) -> list[dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        findings = result.get("findings")
        return list(findings) if isinstance(findings, list) else []

    @staticmethod
    def write_debug_text_artifact_safely(*_args, **_kwargs) -> None:
        return None

    def write_debug_json_artifact_safely(self, _config, path: str, payload: Any) -> None:
        self.artifacts[path] = payload


def finding(
    line: int,
    title: str,
    *,
    severity: str = "medium",
    confidence: float = 0.90,
    risk: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "path": "probe.py",
        "line": line,
        "body": f"Concrete defect {title} is demonstrated by the changed predicate.",
        "suggested_replacement": "",
        "validation": "Run the deterministic issue-524 shape-recovery regression.",
        "_dcoir_v51_candidate_id": f"candidate-{line}",
        "_dcoir_v51_semantic_candidate_key": ["probe.py", line, f"semantic_candidate:candidate-{line}"],
    }
    if risk:
        item["_risk_sentinel_key"] = ["probe.py", line, "python_ssrf"]
    return item


def config() -> SimpleNamespace:
    return SimpleNamespace(
        semantic_adjudication_model_stack=["adjudicator-model"],
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        max_prompt_chars=120000,
        minimum_confidence=0.70,
        max_inline_comments=12,
    )


def module_for(raw: Any):
    hardened = Hardened(raw)
    rank_calls: list[list[dict[str, Any]]] = []

    def ranker(findings: list[dict[str, Any]], cfg: Any) -> list[dict[str, Any]]:
        # The recovery implementation must call the active production ranking
        # boundary with the config object, not slice raw hypotheses directly.
        assert not isinstance(cfg, int)
        rank_calls.append([dict(item) for item in findings])
        required = [item for item in findings if item.get("_risk_sentinel_key")]
        ordinary = [item for item in findings if not item.get("_risk_sentinel_key")]
        return required + ordinary

    module = SimpleNamespace(
        hardened=hardened,
        base=SimpleNamespace(sanitize_text=lambda text, _config: str(text)),
        rank_findings_for_required_budget=ranker,
    )
    return module, hardened, rank_calls


def run(raw: Any, hypotheses: list[dict[str, Any]]):
    module, hardened, rank_calls = module_for(raw)
    reporter = Reporter()
    result = execution.run_adjudicator(
        module,
        {"type": "object"},
        config(),
        reporter,
        hypotheses,
        "exact-head evidence",
        "broader-context",
    )
    return result, module, hardened, rank_calls, reporter


def expect_runtime_error(raw: Any, hypotheses: list[dict[str, Any]], text: str) -> int:
    module, hardened, _rank_calls = module_for(raw)
    reporter = Reporter()
    try:
        execution.run_adjudicator(
            module,
            {"type": "object"},
            config(),
            reporter,
            hypotheses,
            "exact-head evidence",
            "broader-context",
        )
    except RuntimeError as exc:
        assert text in str(exc)
    else:
        raise AssertionError(f"expected fail-closed error containing: {text}")
    return hardened.calls


def main() -> None:
    cfg = config()
    assert v33.verifier_candidate_limit(cfg) == 12

    # Canonical envelopes remain on the historical v37/v35 path.
    canonical = {"summary": "canonical", "findings": [finding(1, "canonical")]}
    (canonical_result, _model, _tier), _module, hardened, rank_calls, reporter = run(
        canonical, [finding(1, "upstream")]
    )
    assert hardened.calls == 1
    assert rank_calls == []
    assert execution.ADJUDICATOR_SHAPE_RECOVERY_MARKER not in canonical_result
    assert canonical_result["findings"][0]["title"] == "canonical"
    assert not any(stage == "semantic-adjudicator-shape-recovery" for stage, _ in reporter.events)

    # v37's existing complete flat-single-finding compatibility remains unchanged.
    flat = finding(2, "flat-compatible")
    (flat_result, _model, _tier), _module, hardened, rank_calls, _reporter = run(
        flat, [finding(3, "upstream")]
    )
    assert hardened.calls == 1
    assert rank_calls == []
    assert flat_result[v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE
    assert execution.ADJUDICATOR_SHAPE_RECOVERY_MARKER not in flat_result

    # A valid JSON object that is neither supported v37 shape recovers only from
    # complete upstream hypotheses. The rejected object's content is not copied.
    upstream = [finding(index, f"candidate-{index}") for index in range(1, 14)]
    upstream.append(finding(99, "required-risk-tail", severity="low", risk=True))
    rejected = {
        "summary": "schema incompatible",
        "issues": ["NEVER_PERSIST_REJECTED_CONTENT"],
        "private": "NEVER_PERSIST_PRIVATE_CONTENT",
    }
    (recovered, model, tier), _module, hardened, rank_calls, reporter = run(
        rejected, upstream
    )
    assert hardened.calls == 1
    assert model == "adjudicator-model"
    assert tier == "default"
    assert len(rank_calls) == 1
    assert len(recovered["findings"]) == 12
    marker = recovered[execution.ADJUDICATOR_SHAPE_RECOVERY_MARKER]
    assert marker["reason"] == "schema-incompatible-valid-json-object"
    assert marker["upstream_hypotheses"] == 14
    assert marker["usable_hypotheses"] == 14
    assert marker["selected_hypotheses"] == 12
    assert marker["verifier_capacity"] == 12
    assert marker["extra_model_calls"] == 0
    assert recovered["findings"][0]["title"] == "required-risk-tail"
    assert recovered["findings"][0]["_risk_sentinel_key"][-1] == "python_ssrf"
    assert recovered["findings"][0]["_dcoir_v51_candidate_id"] == "candidate-99"
    serialized = json.dumps(recovered, sort_keys=True)
    assert "NEVER_PERSIST_REJECTED_CONTENT" not in serialized
    assert "NEVER_PERSIST_PRIVATE_CONTENT" not in serialized
    assert any(
        stage == "semantic-adjudicator-shape-recovery"
        and "extra_model_calls=0" in message
        and "verifier_capacity=12" in message
        for stage, message in reporter.events
    )

    # Incomplete upstream hypotheses are never repaired by inventing fields.
    incomplete = finding(5, "incomplete")
    incomplete.pop("validation")
    calls = expect_runtime_error(
        {"summary": "wrong shape", "issues": []},
        [incomplete],
        "neither a findings envelope nor a complete flat single finding",
    )
    assert calls == 1

    # No usable upstream evidence leaves the original v37 failure fail-closed.
    calls = expect_runtime_error(
        {"summary": "wrong shape", "issues": []},
        [],
        "neither a findings envelope nor a complete flat single finding",
    )
    assert calls == 1

    # Non-object and malformed canonical envelopes retain existing failure paths.
    calls = expect_runtime_error(
        ["not", "an", "object"],
        [finding(6, "upstream")],
        "non-object result",
    )
    assert calls == 1
    calls = expect_runtime_error(
        {"summary": "bad envelope", "findings": "not-a-list"},
        [finding(7, "upstream")],
        "non-list findings",
    )
    assert calls == 1

    print("DCOIR Review issue-524 adjudicator shape-recovery selftest passed")


if __name__ == "__main__":
    main()
