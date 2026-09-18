#!/usr/bin/env python3
"""Regression checks for canonical final inline finding/comment rendering."""

from __future__ import annotations

import hashlib
import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE = ".github/dcoir_review/evaluation/live_verifier_probe.py"
SUGGESTION_PROBE = ".github/dcoir_review/evaluation/live_suggestion_probe.py"
EXPECTED_SHA256 = {
    "verified_ordinary": "e79fa4331b2c598766f341ebf5c03e24b0bc810828d65eebdf3a5ab3795fb0ad",
    "deterministic_repair": "bfe735f9d43f282151462df4a9df3f006a5bf19390dc85be7905446aa1078be4",
    "repair_native": "21709e01b45ce59a0581c8e6aa921552ebb26e0add941208bd802dc5d346e581",
    "repair_fallback": "75beb87ecc18f7914d022d5d444e803bbe6b47f39fc0b0e570d63a5e8d833ac2",
    "unverified_ordinary": "eccde95a51d886006697364bbb213b13216647e21360173e1c926b243719802c",
    "yaml_fallback": "a081f84c530797cb2267bc9a2a810702c94c9ecc4035091ea3ea6193c4af22a7",
}


def _patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def _cases(review):
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    repair = importlib.import_module("dcoir_review.repair_pipeline")
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    cases = {
        "verified_ordinary": {
            "title": "Inverted upper-bound check excludes valid recent ages",
            "severity": "medium",
            "confidence": 0.99,
            "path": PROBE,
            "line": 11,
            "body": "The documented inclusive range is 0 through 60 minutes, but the second comparison uses >= 60 instead of <= 60.",
            "suggested_replacement": "    return age_minutes >= 0 and age_minutes <= 60",
            "validation": f"python3 -m py_compile {PROBE}",
            "fix_guidance": {
                "language": "python",
                "notes": "Reverse the upper-bound comparison so the implementation matches the documented inclusive range.",
            },
            v20.SYNTHESIS_VERIFIED_MARKER: True,
            v21.VERIFIER_MARKER: {
                "mode": "model-judge",
                "supported": True,
                "confidence": 0.99,
                "evidence": "range contradiction",
                "head_sha": "probe-head",
                "line": 11,
            },
        },
        "deterministic_repair": {
            "title": "model wording should not replace deterministic sentinel template",
            "severity": "high",
            "confidence": 0.99,
            "path": SUGGESTION_PROBE,
            "line": 10,
            "body": "model body should not replace deterministic sentinel detail",
            "suggested_replacement": '    if severity in {"critical", "high"}:',
            "_anchored_line_text": '    if severity == "critical" or "high":',
            "_risk_sentinel_key": [SUGGESTION_PROBE, 10, v20.PYTHON_TRUTHY_LITERAL_BRANCH],
            "_risk_sentinel_kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
            v21.VERIFIER_MARKER: {
                "mode": "deterministic-core-sentinel",
                "supported": True,
                "kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
                "head_sha": "probe-head",
                "line": 10,
            },
            repair.REPAIR_MARKER: {
                "version": "v30",
                "outcome": "native-suggestion",
                "path": SUGGESTION_PROBE,
                "line": 10,
            },
        },
        "repair_native": {
            "title": "Upper-bound comparison is inverted",
            "severity": "high",
            "confidence": 0.99,
            "path": PROBE,
            "line": 12,
            "body": "The function documents an inclusive 0..60 range, but this line requires age_minutes to be at least 60 for the upper-bound term.",
            "suggested_replacement": "    return age_minutes >= 0 and age_minutes <= 60",
            "validation": f"python3 -m py_compile {PROBE}",
            v21.VERIFIER_MARKER: {
                "mode": "model-judge",
                "supported": True,
                "confidence": 0.99,
                "evidence": "range contradiction",
                "head_sha": "probe-head",
                "line": 12,
            },
            repair.REPAIR_MARKER: {
                "version": repair.VERSION,
                "outcome": "native-suggestion",
                "path": PROBE,
                "line": 12,
                "critic_accepted": True,
                "critic_confidence": 0.99,
            },
        },
        "repair_fallback": {
            "title": "Upper-bound comparison is inverted",
            "severity": "high",
            "confidence": 0.99,
            "path": PROBE,
            "line": 12,
            "body": "Verified boundary-condition issue.",
            "suggested_replacement": "",
            "fix_guidance": {"language": "py", "notes": "No safe exact one-line fix was proven."},
            v21.VERIFIER_MARKER: {
                "mode": "model-judge",
                "supported": True,
                "confidence": 0.99,
                "evidence": "range contradiction",
                "head_sha": "probe-head",
                "line": 12,
            },
            repair.REPAIR_MARKER: {
                "version": repair.VERSION,
                "outcome": "no-safe-single-line-fix",
                "path": PROBE,
                "line": 12,
            },
        },
        "unverified_ordinary": {
            "title": "Unverified ordinary probe",
            "severity": "medium",
            "confidence": 0.99,
            "path": PROBE,
            "line": 11,
            "body": "ordinary semantic text without verifier support",
            "suggested_replacement": "",
            "validation": f"python3 -m py_compile {PROBE}",
        },
        "deterministic_no_repair": {
            "title": "model wording",
            "severity": "high",
            "confidence": 0.99,
            "path": SUGGESTION_PROBE,
            "line": 10,
            "body": "model body",
            "suggested_replacement": '    if severity == "critical" or severity == "high":',
            "fix_guidance": {
                "language": "python",
                "notes": "MODEL CONTROLLED GUIDANCE MUST NOT RENDER",
            },
            v20.SYNTHESIS_VERIFIED_MARKER: True,
            "_risk_sentinel_key": [SUGGESTION_PROBE, 10, v20.PYTHON_TRUTHY_LITERAL_BRANCH],
            "_risk_sentinel_kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
            v21.VERIFIER_MARKER: {
                "mode": "deterministic-core-sentinel",
                "supported": True,
                "kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
                "head_sha": "probe-head",
                "line": 10,
            },
        },
    }
    sentinel = review.hardened.RiskSentinel(
        path=".github/workflows/probe.yml",
        line=4,
        label="GitHub Actions workflow grants broad write permissions",
        detail="write-all grants broad token access",
        text="permissions: write-all",
    )
    fallback = review.hardened.add_risk_sentinel_fallback_findings([], [sentinel], config, [])
    assert len(fallback) == 1, fallback
    cases["yaml_fallback"] = fallback[0]
    return config, cases


def main() -> None:
    review = _patched_review()
    assert review.base.build_inline_comment.__module__ == "dcoir_review.finding_comment_render"
    stored = [
        name for name, value in vars(review.base).items()
        if name.startswith("_dcoir_") and "build_inline_comment" in name and callable(value)
    ]
    assert stored == [], stored

    config, cases = _cases(review)
    observed = {}
    for name, finding in cases.items():
        rendered = review.base.build_inline_comment(dict(finding), "test-model", config)
        if name == "deterministic_no_repair":
            assert "MODEL CONTROLLED GUIDANCE MUST NOT RENDER" not in rendered, rendered
            assert "**Validation:**" in rendered, rendered
            assert f"python3 -m py_compile {SUGGESTION_PROBE}" in rendered, rendered
            assert f"bandit -r {SUGGESTION_PROBE}" in rendered, rendered
            continue
        observed[name] = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert observed == EXPECTED_SHA256, {"expected": EXPECTED_SHA256, "observed": observed}
    print("dcoir_review_finding_comment_render_selftest passed")


if __name__ == "__main__":
    main()
