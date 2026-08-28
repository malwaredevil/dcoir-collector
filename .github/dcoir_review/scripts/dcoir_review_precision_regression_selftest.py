#!/usr/bin/env python3
"""Evaluate DCOIR Review deterministic precision corpus v1."""

from __future__ import annotations

import json
from pathlib import Path

import dcoir_review_required_runtime_patch_v16 as v16
import openrouter_pr_review_pareto_context as review
from dcoir_review.entrypoint import DcoirReviewEntrypoint


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "evaluation" / "precision_corpus_v1.json"
TRUTHY_BRANCH_LABEL = "truthy literal branch condition"


def _diff(path: str, source: str) -> str:
    lines = source.splitlines() or [""]
    body = "\n".join(f"+{line}" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 0000000..1111111 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}\n"
    )


def _sentinels(path: str, source: str):
    return review.detect_risk_sentinels(_diff(path, source))


def _has_python_dynamic_exec(path: str, source: str) -> bool:
    return any(v16._sentinel_key(item)[2] == v16.PYTHON_DYNAMIC_EXEC for item in _sentinels(path, source))


def _has_truthy_branch(path: str, source: str) -> bool:
    return any(str(getattr(item, "label", "")) == TRUTHY_BRANCH_LABEL for item in _sentinels(path, source))


def _has_label(path: str, source: str, label: str) -> bool:
    return any(str(getattr(item, "label", "")) == label for item in _sentinels(path, source))


def main() -> None:
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert corpus.get("schema_version") == "dcoir_review_precision_corpus_v1"
    fixtures = corpus.get("fixtures")
    assert isinstance(fixtures, list) and fixtures

    metrics = {
        "schema_version": "dcoir_review_precision_metrics_v1",
        "fixture_count": len(fixtures),
        "known_false_positive_count": 0,
        "known_false_positives_suppressed": 0,
        "known_true_positive_count": 0,
        "known_true_positives_retained": 0,
        "context_precision_count": 0,
        "context_precision_passed": 0,
        "regressions": [],
    }

    for fixture in fixtures:
        fixture_id = str(fixture.get("id", "<missing-id>"))
        classification = str(fixture.get("classification", ""))
        check = str(fixture.get("check", ""))
        passed = False

        if check == "python_dynamic_exec_absent":
            metrics["known_false_positive_count"] += 1
            passed = not _has_python_dynamic_exec(str(fixture["path"]), str(fixture["source"]))
            metrics["known_false_positives_suppressed"] += int(passed)
        elif check == "python_dynamic_exec_present":
            metrics["known_true_positive_count"] += 1
            passed = _has_python_dynamic_exec(str(fixture["path"]), str(fixture["source"]))
            metrics["known_true_positives_retained"] += int(passed)
        elif check == "truthy_branch_absent":
            metrics["known_false_positive_count"] += 1
            passed = not _has_truthy_branch(str(fixture["path"]), str(fixture["source"]))
            metrics["known_false_positives_suppressed"] += int(passed)
        elif check == "truthy_branch_present":
            metrics["known_true_positive_count"] += 1
            passed = _has_truthy_branch(str(fixture["path"]), str(fixture["source"]))
            metrics["known_true_positives_retained"] += int(passed)
        elif check == "risk_label_absent":
            metrics["known_false_positive_count"] += 1
            passed = not _has_label(str(fixture["path"]), str(fixture["source"]), str(fixture["label"]))
            metrics["known_false_positives_suppressed"] += int(passed)
        elif check == "risk_label_present":
            metrics["known_true_positive_count"] += 1
            passed = _has_label(str(fixture["path"]), str(fixture["source"]), str(fixture["label"]))
            metrics["known_true_positives_retained"] += int(passed)
        elif check == "deep_context_priority":
            metrics["context_precision_count"] += 1
            preferred = dict(fixture["preferred"])
            deprioritized = dict(fixture["deprioritized"])
            passed = review.deep_context_priority(preferred) < review.deep_context_priority(deprioritized)
            metrics["context_precision_passed"] += int(passed)
        else:
            metrics["regressions"].append({"id": fixture_id, "reason": f"unknown check {check!r}"})
            continue

        if not passed:
            metrics["regressions"].append({"id": fixture_id, "classification": classification, "check": check})

    if metrics["known_false_positive_count"]:
        metrics["false_positive_suppression_rate"] = (
            metrics["known_false_positives_suppressed"] / metrics["known_false_positive_count"]
        )
    if metrics["known_true_positive_count"]:
        metrics["true_positive_retention_rate"] = (
            metrics["known_true_positives_retained"] / metrics["known_true_positive_count"]
        )

    print(json.dumps(metrics, indent=2, sort_keys=True))
    if metrics["regressions"]:
        raise AssertionError(f"DCOIR precision corpus regressions: {metrics['regressions']}")


if __name__ == "__main__":
    main()
