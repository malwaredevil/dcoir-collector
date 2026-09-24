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
    "deterministic_repair": "e169e713ad2e4ca9607229c640fc9e77cc7479b0d8e9060856d350994bed0a7f",
    "repair_native": "21709e01b45ce59a0581c8e6aa921552ebb26e0add941208bd802dc5d346e581",
    "repair_fallback": "fb036ec9fb6a2bf4c4bd713c552d5d875b21cd38d3ca0566fc7e26f871b36800",
    "unverified_ordinary": "326e95f6333543744d865435f5927083c2f7103235a2710f831b8406ec50258b",
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
        "deterministic_declined": {
            "title": "model wording",
            "severity": "high",
            "confidence": 0.99,
            "path": SUGGESTION_PROBE,
            "line": 10,
            "body": "model body",
            "suggested_replacement": "",
            "fix_guidance": {
                "language": "python",
                "notes": "MODEL REPAIR RATIONALE MUST NOT RENDER",
            },
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
                "version": "v36",
                "outcome": "verified-no-safe-repair-set",
                "path": SUGGESTION_PROBE,
                "line": 10,
                "reason": "MODEL REPAIR RATIONALE MUST NOT RENDER",
            },
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
    renderer = importlib.import_module("dcoir_review.finding_comment_render")
    repair = importlib.import_module("dcoir_review.repair_pipeline")
    for outcome, expected in (
        ("repair-stage-failed-closed", "failed closed"),
        ("verified-repair-budget-deferred", "repair budget was exhausted"),
        ("verified-repair-confidence-deferred", "repair-confidence floor"),
    ):
        disposition = renderer._deterministic_repair_disposition(
            {repair.REPAIR_MARKER: {"outcome": outcome, "reason": "MODEL TEXT"}}
        )
        assert expected in disposition
        assert "MODEL TEXT" not in disposition
    precritic = renderer._deterministic_repair_disposition(
        {repair.REPAIR_MARKER: {"outcome": "verified-no-safe-repair-set", "reason": "MODEL TEXT"}}
    )
    assert "critic-eligible" in precritic
    assert "MODEL TEXT" not in precritic
    author_declined = renderer._deterministic_repair_disposition(
        {repair.REPAIR_MARKER: {"outcome": "author-declined", "reason": "MODEL TEXT"}}
    )
    assert "critic-eligible" in author_declined
    assert "MODEL TEXT" not in author_declined
    critic_rejected = renderer._deterministic_repair_disposition(
        {
            repair.REPAIR_MARKER: {
                "outcome": "verified-no-safe-repair-set",
                "critic_model": "openai/gpt-5.6-sol-pro",
                "critic_confidence": 0.90,
                "reason": "MODEL TEXT",
            }
        }
    )
    assert "critic rejected" in critic_rejected
    assert "MODEL TEXT" not in critic_rejected
    postcritic = renderer._deterministic_repair_disposition(
        {
            repair.REPAIR_MARKER: {
                "outcome": "verified-no-safe-repair-set",
                "critic_model": "openai/gpt-5.6-sol-pro",
                "critic_accepted": True,
                "reason": "MODEL TEXT",
            }
        }
    )
    assert "exact-head revalidation" in postcritic
    assert "MODEL TEXT" not in postcritic
    model_declined = dict(cases["repair_fallback"])
    model_declined["fix_guidance"] = {"language": "py", "notes": "MODEL REPAIR RATIONALE MUST NOT RENDER"}
    model_declined[repair.REPAIR_MARKER] = {
        "version": "v56",
        "outcome": "verified-no-safe-repair-set",
        "critic_model": "openai/gpt-5.6-sol-pro",
        "critic_confidence": 0.95,
        "critic_failed_closed": False,
        "reason": "MODEL CRITIC RATIONALE MUST NOT RENDER",
    }
    rendered_declined = review.base.build_inline_comment(model_declined, "test-model", config)
    assert "critic rejected" in rendered_declined
    assert "MODEL REPAIR RATIONALE MUST NOT RENDER" not in rendered_declined
    assert "MODEL CRITIC RATIONALE MUST NOT RENDER" not in rendered_declined
    model_failed = dict(cases["repair_fallback"])
    model_failed["fix_guidance"] = {"language": "py", "notes": "MODEL FAILURE DETAIL MUST NOT RENDER"}
    model_failed[repair.REPAIR_MARKER] = {
        "version": "v56",
        "outcome": "repair-stage-failed-closed",
        "critic_model": "openai/gpt-5.6-sol-pro",
        "critic_failed_closed": True,
        "reason": "PROVIDER EXCEPTION MUST NOT RENDER",
    }
    rendered_failed = review.base.build_inline_comment(model_failed, "test-model", config)
    assert "failed closed" in rendered_failed
    assert "MODEL FAILURE DETAIL MUST NOT RENDER" not in rendered_failed
    assert "PROVIDER EXCEPTION MUST NOT RENDER" not in rendered_failed

    observed = {}
    for name, finding in cases.items():
        rendered = review.base.build_inline_comment(dict(finding), "test-model", config)
        if name == "deterministic_no_repair":
            assert "MODEL CONTROLLED GUIDANCE MUST NOT RENDER" not in rendered, rendered
            assert "**Validation:**" in rendered, rendered
            assert f"python3 -m py_compile {SUGGESTION_PROBE}" in rendered, rendered
            assert f"bandit -r {SUGGESTION_PROBE}" in rendered, rendered
            continue
        if name == "deterministic_declined":
            assert "MODEL REPAIR RATIONALE MUST NOT RENDER" not in rendered, rendered
            assert "Repair synthesis did not produce a critic-eligible complete repair set" in rendered, rendered
            continue
        observed[name] = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert observed == EXPECTED_SHA256, {"expected": EXPECTED_SHA256, "observed": observed}
    print("dcoir_review_finding_comment_render_selftest passed")


if __name__ == "__main__":
    main()
