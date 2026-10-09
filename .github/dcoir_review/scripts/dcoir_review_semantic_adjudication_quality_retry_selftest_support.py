#!/usr/bin/env python3
"""Shared harness for the final semantic-adjudication quality-retry selftests."""

from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint

RETRY_MARKER = "Review quality retry:"
LINES = {("probe.py", 12): 1}
INITIAL_MODEL = "adjudicator-model"
RETRY_MODEL = "retry-adjudicator-model"
CLEAN = {"summary": "No remaining actionable findings.", "findings": []}


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def load_review() -> Any:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def finding(confidence: Any = 0.60, **overrides: Any) -> dict[str, Any]:
    """Return a complete adjudicator finding; ``confidence=None`` omits it."""

    item = {
        "path": "probe.py",
        "line": 12,
        "severity": "medium",
        "title": "Source scope conflict",
        "body": "The changed rule still narrows by an alert label alone.",
        "suggested_replacement": "",
        "validation": "Compare the added rule with the unchanged routing condition.",
    }
    if confidence is not None:
        item["confidence"] = confidence
    item.update(overrides)
    return item


def response(*findings: Any, summary: Any = "The changed lines back the conflict.") -> dict[str, Any]:
    return {"summary": summary, "findings": list(findings)}


def detector(*_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], str, str]:
    return response(finding(0.94, line=10), finding(0.90, line=11)), "detector-model", "default"


def low_confidence_reason(result: dict[str, Any], _cfg: Any, _sentinels: Any, _lines: Any) -> str:
    for item in result.get("findings", []):
        value = item.get("confidence") if isinstance(item, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0.70:
            return "no finding meets confidence 0.70"
    return ""


def always_retry(*_args: Any) -> str:
    return "no finding meets confidence 0.70"


def forbidden_merge(**_kwargs: Any) -> dict[str, Any]:
    raise AssertionError("malformed provider output reached retry result merging")


def base_config(**overrides: Any) -> SimpleNamespace:
    config = SimpleNamespace(
        semantic_adjudication_review=True,
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        semantic_adjudication_model_stack=[INITIAL_MODEL],
        max_prompt_chars=120000,
        minimum_confidence=0.70,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


class Harness:
    """Run the canonical adjudication stage against scripted provider replies."""

    def __init__(self, review: Any) -> None:
        self.review = review
        self.adjudication = importlib.import_module("dcoir_review.semantic_adjudication")
        self.debug_text: dict[str, str] = {}
        self.debug_json: dict[str, Any] = {}
        self.reporter = Reporter()
        self.calls: list[str] = []
        self.model_label = ""

    def run(
        self,
        initial: Any,
        retry: Any = None,
        *,
        reason: Any = low_confidence_reason,
        merge: Any = None,
        config: Any = None,
        line_index: Any = None,
    ) -> dict[str, Any]:
        calls: list[str] = []
        self.calls = calls

        def provider(prompt: str, _schema: Any, _cfg: Any, _reporter: Any = None):
            calls.append(prompt)
            is_retry = RETRY_MARKER in prompt
            reply = retry if is_retry else initial
            if isinstance(reply, Exception):
                raise reply
            return copy.deepcopy(reply), RETRY_MODEL if is_retry else INITIAL_MODEL, "default"

        hardened = SimpleNamespace(
            parse_yaml_like_data=lambda _path: {},
            bool_value=lambda _data, _key, default: default,
            write_debug_text_artifact_safely=lambda _cfg, path, text: self.debug_text.__setitem__(path, text),
            write_debug_json_artifact_safely=lambda _cfg, path, payload: self.debug_json.__setitem__(path, payload),
            openrouter_review=provider,
            result_findings=lambda result: list(result.get("findings", [])),
            ReviewQualityError=RuntimeError,
            review_quality_retry_reason=reason,
            build_quality_retry_prompt=lambda prompt, _prior, _s, _c, why: f"{RETRY_MARKER} {why}\n{prompt}",
            merge_quality_retry_results=merge or self.review.hardened.merge_quality_retry_results,
            raw_findings_digest=self.review.hardened.raw_findings_digest,
            sanitize_github_output=lambda text, _cfg: str(text),
        )
        module = SimpleNamespace(
            openrouter_review_with_hybrid_first_pass=detector,
            hardened=hardened,
            base=SimpleNamespace(sanitize_text=lambda text, _cfg: str(text)),
            build_prompt=lambda *_args, **_kwargs: "PR EVIDENCE: changed predicate and tests",
            rank_findings_for_required_budget=lambda items, limit: items[:limit],
        )
        stage = self.adjudication.build_semantic_adjudication_stage(module, detector)
        result, self.model_label, _tier = stage(
            {"number": 1}, [], "diff", {}, config or base_config(), self.reporter,
            [], LINES if line_index is None else line_index, "", "deep-forced", "", object(),
        )
        return result

    def expect_failure(self, fragment: str, *args: Any, **kwargs: Any) -> None:
        try:
            self.run(*args, **kwargs)
        except RuntimeError as exc:
            assert fragment in str(exc), str(exc)
            return
        raise AssertionError(f"expected a fail-closed quality error containing {fragment!r}")
