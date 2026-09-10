#!/usr/bin/env python3
"""Deterministic regression checks for DCOIR Review v55 shape recovery."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v37 as v37
import dcoir_review_required_runtime_patch_v44_execution as execution
import dcoir_review_required_runtime_patch_v44_scope as scope
import dcoir_review_required_runtime_patch_v51 as v51
import dcoir_review_required_runtime_patch_v55 as v55


ROOT = Path(__file__).resolve().parent.parent


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
        self.stage_labels: list[str] = []
        self.artifacts: dict[str, Any] = {}

    def openrouter_review(self, _prompt, _schema, config, _reporter=None):
        self.calls += 1
        self.stage_labels.append(str(getattr(config, v55._V54_STAGE_LABEL_ATTR, "") or ""))
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
        "validation": "Run the deterministic v55 shape-recovery regression.",
        "_dcoir_v51_candidate_id": f"candidate-{line}",
        "_dcoir_v51_semantic_candidate_key": [
            "probe.py",
            line,
            f"semantic_candidate:candidate-{line}",
        ],
    }
    if risk:
        item["_risk_sentinel_key"] = ["probe.py", line, "python_ssrf"]
    return item


def config() -> SimpleNamespace:
    return SimpleNamespace(
        semantic_adjudication_model_stack=["adjudicator-model"],
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        semantic_candidate_identity_review=True,
        max_prompt_chars=120000,
        minimum_confidence=0.70,
        max_inline_comments=12,
    )


def module_for(raw: Any):
    hardened = Hardened(raw)
    rank_calls: list[list[dict[str, Any]]] = []

    def ranker(findings: list[dict[str, Any]], cfg: Any) -> list[dict[str, Any]]:
        # Recovery must use the active production ranker with config rather than
        # slicing raw upstream hypotheses by ordinal.
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
    result = v55.run_adjudicator(
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
        v55.run_adjudicator(
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


def production_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def production_config(review):
    return review.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.telemetry_patch_module_names == (
        "dcoir_review_required_runtime_patch_v54",
    )
    assert entrypoint.post_telemetry_patch_module_names[0] == "dcoir_review_required_runtime_patch_v55"
    assert entrypoint.post_telemetry_patch_module_names.index("dcoir_review_required_runtime_patch_v55") < entrypoint.post_telemetry_patch_module_names.index("dcoir_review_required_runtime_patch_v56")

    # v55 owns a new terminal seam rather than mutating the versioned v44 helper.
    original = getattr(execution, v55.RUN_STORAGE, None) or execution.run_adjudicator
    fake_apply_module = SimpleNamespace()
    v55.apply_pareto_context_module(fake_apply_module)
    assert getattr(fake_apply_module, v55.APPLIED_MARKER, False) is True
    assert execution.run_adjudicator is v55.run_adjudicator
    assert getattr(execution, v55.RUN_STORAGE) is original
    v55.apply_pareto_context_module(fake_apply_module)
    assert getattr(execution, v55.RUN_STORAGE) is original

    cfg = config()
    assert v33.verifier_candidate_limit(cfg) == 12

    # Canonical envelopes remain on the historical v37/v35 path.
    canonical = {"summary": "canonical", "findings": [finding(1, "canonical")]}
    (canonical_result, _model, _tier), _module, hardened, rank_calls, reporter = run(
        canonical, [finding(1, "upstream")]
    )
    assert hardened.calls == 1
    assert hardened.stage_labels == ["semantic-adjudicator"]
    assert rank_calls == []
    assert v55.RECOVERY_MARKER not in canonical_result
    assert canonical_result["findings"][0]["title"] == "canonical"
    assert not any(stage == "semantic-adjudicator-shape-recovery" for stage, _ in reporter.events)

    # v37's complete flat-single-finding compatibility remains unchanged.
    flat = finding(2, "flat-compatible")
    (flat_result, _model, _tier), _module, hardened, rank_calls, _reporter = run(
        flat, [finding(3, "upstream")]
    )
    assert hardened.calls == 1
    assert hardened.stage_labels == ["semantic-adjudicator"]
    assert rank_calls == []
    assert flat_result[v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE
    assert v55.RECOVERY_MARKER not in flat_result

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
    assert hardened.stage_labels == ["semantic-adjudicator"]
    assert model == "adjudicator-model"
    assert tier == "default"
    assert len(rank_calls) == 1
    assert len(recovered["findings"]) == 12
    marker = recovered[v55.RECOVERY_MARKER]
    assert marker["reason"] == v55.RECOVERY_REASON
    assert marker["upstream_hypotheses"] == 14
    assert marker["usable_hypotheses"] == 14
    assert marker["deduped_hypotheses"] == 14
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

    # v51 may remove untrusted detector replacement text while preserving the
    # semantic candidate. That must not make the candidate ineligible for v55.
    v51_candidate = finding(100, "v51-preserved-semantic-candidate")
    v51_candidate.pop("suggested_replacement")
    (v51_recovered, _model, _tier), _module, hardened, rank_calls, _reporter = run(
        rejected, [v51_candidate]
    )
    assert hardened.calls == 1
    assert len(rank_calls) == 1
    assert len(v51_recovered["findings"]) == 1
    assert "suggested_replacement" not in v51_recovered["findings"][0]
    assert v51_recovered["findings"][0]["_dcoir_v51_candidate_id"] == "candidate-100"

    # Exact semantic duplicates collapse, but distinct same-site/same-title
    # hypotheses must survive into the active production v51-aware ranker.
    review = production_review()
    prod_cfg = production_config(review)
    assert prod_cfg.semantic_candidate_identity_review is True
    # Production v55 must patch v44's earlier scope dedupe, not merely the
    # recovery helper, so same-site semantic candidates survive before the
    # adjudicator/recovery seam is reached.
    assert scope.dedupe_exact_findings is v55._dedupe_upstream_hypotheses
    first = finding(101, "same-site-semantic-candidate")
    second = finding(101, "same-site-semantic-candidate")
    for item in (first, second):
        item.pop(v51.CANDIDATE_ID_FIELD, None)
        item.pop("suggested_replacement", None)
    first["body"] = "Primary semantic defect at the shared changed line remains independently actionable."
    first["validation"] = "Run the first same-site semantic invariant regression."
    first[v51.SEMANTIC_KEY_FIELD] = [
        "probe.py",
        101,
        f"{v51.SEMANTIC_KIND_PREFIX}same-site-primary",
    ]
    second["body"] = "A distinct fallback semantic defect at the same changed line has different impact."
    second["validation"] = "Run the second same-site semantic invariant regression."
    second[v51.SEMANTIC_KEY_FIELD] = [
        "probe.py",
        101,
        f"{v51.SEMANTIC_KIND_PREFIX}same-site-fallback",
    ]
    deduped = scope.dedupe_exact_findings([first, dict(first), second])
    assert len(deduped) == 2
    recovered_identity = v55._recover_upstream_hypotheses(
        review, [first, dict(first), second], prod_cfg
    )
    assert recovered_identity is not None
    identity_findings = recovered_identity["findings"]
    assert len(identity_findings) == 2
    assert all(v55._complete_upstream_hypothesis(review, item) for item in identity_findings)
    candidate_ids = [str(item.get(v51.CANDIDATE_ID_FIELD, "")) for item in identity_findings]
    semantic_keys = [tuple(item.get(v51.SEMANTIC_KEY_FIELD, [])) for item in identity_findings]
    assert len(set(candidate_ids)) == 2
    assert len(set(semantic_keys)) == 2
    identity_marker = recovered_identity[v55.RECOVERY_MARKER]
    assert identity_marker["upstream_hypotheses"] == 3
    assert identity_marker["usable_hypotheses"] == 3
    assert identity_marker["deduped_hypotheses"] == 2
    assert identity_marker["selected_hypotheses"] == 2
    assert identity_marker["selected_hypotheses"] <= identity_marker["verifier_capacity"]

    # Oversized JSON integers can overflow float conversion. They are rejected as
    # unusable upstream evidence rather than escaping the fallback candidate filter.
    oversized = finding(102, "oversized-confidence")
    oversized["confidence"] = 10**400
    assert v55._complete_upstream_hypothesis(review, oversized) is False
    calls = expect_runtime_error(
        rejected,
        [oversized],
        "neither a findings envelope nor a complete flat single finding",
    )
    assert calls == 1

    # Incomplete or schema-invalid semantic fields are never repaired/coerced.
    incomplete = finding(5, "incomplete")
    incomplete.pop("validation")
    calls = expect_runtime_error(
        {"summary": "wrong shape", "issues": []},
        [incomplete],
        "neither a findings envelope nor a complete flat single finding",
    )
    assert calls == 1
    nonnumeric = finding(6, "nonnumeric")
    nonnumeric["confidence"] = "0.95"
    calls = expect_runtime_error(
        {"summary": "wrong shape", "issues": []},
        [nonnumeric],
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

    # A partial flat finding remains malformed under v37 and never becomes an
    # upstream-hypothesis fallback merely because it is valid JSON.
    partial_flat = finding(7, "partial-flat")
    partial_flat.pop("validation")
    calls = expect_runtime_error(
        partial_flat,
        [finding(8, "usable-upstream")],
        "neither a findings envelope nor a complete flat single finding",
    )
    assert calls == 1

    # Non-object and malformed canonical envelopes retain existing failure paths.
    calls = expect_runtime_error(
        ["not", "an", "object"],
        [finding(9, "upstream")],
        "non-object result",
    )
    assert calls == 1
    calls = expect_runtime_error(
        {"summary": "bad envelope", "findings": "not-a-list"},
        [finding(10, "upstream")],
        "non-list findings",
    )
    assert calls == 1

    print("DCOIR Review v55 adjudicator shape-recovery selftest passed")


if __name__ == "__main__":
    main()
