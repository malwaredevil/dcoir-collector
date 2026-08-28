#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v19 suggestion/precision overlay."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v19 as v19
import openrouter_pr_review as base


class FakeReviewQualityError(RuntimeError):
    pass


class FakeHardened:
    ReviewQualityError = FakeReviewQualityError

    def __init__(self) -> None:
        self.artifacts: dict[str, Any] = {}

    def write_debug_json_artifact_safely(self, _config: Any, path: str, data: Any) -> None:
        self.artifacts[path] = data


class FakeReporter:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str]] = []

    def update(self, stage: str, detail: str) -> None:
        self.updates.append((stage, detail))


def _module_returning(enriched: list[dict[str, Any]]) -> tuple[SimpleNamespace, FakeHardened, FakeReporter]:
    hardened = FakeHardened()
    reporter = FakeReporter()

    def original(_findings, _gh, _pr, _schema, _config, _reporter):
        return [dict(item) for item in enriched]

    module = SimpleNamespace(hardened=hardened, synthesize_fixes_for_findings=original)
    v19.apply_pareto_context_module(module)
    return module, hardened, reporter


def test_fix_synthesis_false_positive_contradiction_fails_closed() -> None:
    finding = {
        "path": "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py",
        "line": 26,
        "title": "Python executes caller-controlled code",
        "body": "This line evaluates text as Python code.",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "python",
            "notes": (
                "Line 26 assigns a compiled regular expression constant and contains no dynamic code evaluation. "
                "The finding appears to be a false positive at the anchored line and should be dispositioned "
                "or dismissed rather than modified with a code change."
            ),
        },
    }
    module, hardened, reporter = _module_returning([finding])
    try:
        module.synthesize_fixes_for_findings([finding], object(), {"head": {"sha": "abc"}}, {}, SimpleNamespace(), reporter)
    except FakeReviewQualityError as exc:
        text = str(exc)
        assert "refused to publish self-contradictory findings" in text
        assert "build_openai_gpt_deployment_release.py:26" in text
    else:
        raise AssertionError("self-disqualifying fix synthesis must fail closed")

    artifact = hardened.artifacts[v19.OUTCOME_ARTIFACT]
    assert artifact["self_disqualified_count"] == 1
    assert artifact["native_suggestion_count"] == 0
    assert artifact["findings"][0]["self_disqualification_reason"]
    assert any(stage == "fix-synthesis" and "quality contradiction" in detail for stage, detail in reporter.updates)


def test_normal_fix_guidance_is_not_self_disqualifying() -> None:
    finding = {
        "path": "tools/example.py",
        "line": 7,
        "title": "Bound the caller-provided limit",
        "body": "The caller can request an unbounded result set.",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "python",
            "replace": "limit = min(limit, 100)",
            "notes": "Cap the requested result count before the query is issued.",
        },
    }
    assert v19.fix_synthesis_self_disqualification_reason(finding) == ""
    module, hardened, reporter = _module_returning([finding])
    result = module.synthesize_fixes_for_findings([finding], object(), {"head": {"sha": "abc"}}, {}, SimpleNamespace(), reporter)
    assert result[0]["title"] == finding["title"]
    artifact = hardened.artifacts[v19.OUTCOME_ARTIFACT]
    assert artifact["fallback_guidance_count"] == 1
    assert artifact["self_disqualified_count"] == 0


def test_safe_native_suggestion_is_recorded_and_renders_github_suggestion_fence() -> None:
    finding = {
        "path": "tools/example.py",
        "line": 7,
        "severity": "medium",
        "confidence": 0.95,
        "title": "Bound the caller-provided limit",
        "body": "The caller can request an unbounded result set.",
        "suggested_replacement": "limit = min(limit, 100)",
        "validation": "python3 -m py_compile tools/example.py",
    }
    module, hardened, reporter = _module_returning([finding])
    result = module.synthesize_fixes_for_findings([finding], object(), {"head": {"sha": "abc"}}, {}, SimpleNamespace(), reporter)
    assert result[0]["suggested_replacement"] == "limit = min(limit, 100)"
    artifact = hardened.artifacts[v19.OUTCOME_ARTIFACT]
    assert artifact["native_suggestion_count"] == 1
    assert artifact["findings"][0]["outcome"] == "native-suggestion"

    config = base.load_yaml_like_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    rendered = base.build_inline_comment(result[0], "test-model", config)
    assert "```suggestion\nlimit = min(limit, 100)\n```" in rendered
    assert "Suggested fix:" in rendered


def test_detector_text_alone_cannot_self_disqualify_after_synthesis() -> None:
    finding = {
        "path": "tools/example.py",
        "line": 9,
        "title": "Explain false-positive suppression",
        "body": "This code documents the phrase false positive but the synthesized repair is concrete.",
        "suggested_replacement": "value = sanitize(value)",
        "fix_guidance": {},
    }
    assert v19.fix_synthesis_self_disqualification_reason(finding) == ""


def main() -> None:
    test_fix_synthesis_false_positive_contradiction_fails_closed()
    test_normal_fix_guidance_is_not_self_disqualifying()
    test_safe_native_suggestion_is_recorded_and_renders_github_suggestion_fence()
    test_detector_text_alone_cannot_self_disqualify_after_synthesis()
    print("dcoir_review_required_runtime_patch_v19_selftest passed")


if __name__ == "__main__":
    main()
