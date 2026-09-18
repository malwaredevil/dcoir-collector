#!/usr/bin/env python3
"""Regression self-test for the stable DCOIR Review precision guard."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dcoir_review import precision_guard
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

    module = SimpleNamespace(hardened=hardened)

    def composed(_findings, _gh, _pr, _schema, config, active_reporter):
        repaired = [dict(item) for item in enriched]
        return precision_guard.enforce_fix_synthesis_precision(
            module, config, repaired, active_reporter
        )

    module.synthesize_fixes_for_findings = composed
    return module, hardened, reporter


def test_language_scoped_sentinel_filter_suppresses_cross_language_fixture_text() -> None:
    false_python_powershell = SimpleNamespace(
        path="project_sources/collector/tools/test_run_powershell_function_reachability_report.py",
        line=293,
        label="PowerShell Invoke-Expression",
        detail="fixture text only",
        text='"text": "Invoke-Expression $scriptText"',
    )
    real_powershell = SimpleNamespace(
        path="tools/probe.ps1",
        line=7,
        label="PowerShell Invoke-Expression",
        detail="real PowerShell execution primitive",
        text="Invoke-Expression $scriptText",
    )
    generic_python = SimpleNamespace(
        path="tools/probe.py",
        line=9,
        label="truthy literal branch condition",
        detail="generic cross-language condition rule",
        text='if severity == "critical" or "high":',
    )

    filtered = precision_guard.filter_language_scoped_sentinels(
        [false_python_powershell, real_powershell, generic_python]
    )

    assert false_python_powershell not in filtered
    assert real_powershell in filtered
    assert generic_python in filtered
    assert not precision_guard.sentinel_matches_source_language(false_python_powershell)
    assert precision_guard.sentinel_matches_source_language(real_powershell)


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

    artifact = hardened.artifacts[precision_guard.OUTCOME_ARTIFACT]
    assert artifact["self_disqualified_count"] == 1
    assert artifact["native_suggestion_count"] == 0
    assert artifact["findings"][0]["self_disqualification_reason"]
    assert any(stage == "fix-synthesis" and "quality contradiction" in detail for stage, detail in reporter.updates)


def test_live_no_code_modification_wording_fails_closed() -> None:
    finding = {
        "path": "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py",
        "line": 26,
        "title": "Python executes caller-controlled code",
        "body": "This line evaluates text as Python code.",
        "suggested_replacement": "",
        "fix_guidance": {
            "language": "python",
            "notes": (
                "Line 26 defines a static regular expression constant using re.compile on a fixed string literal. "
                "It does not evaluate dynamic expressions or execute caller-controlled Python code. "
                "No code modification is required for this line."
            ),
        },
    }
    assert precision_guard.fix_synthesis_self_disqualification_reason(finding) == precision_guard.WEAK_NO_REPAIR_REASON
    module, _hardened, reporter = _module_returning([finding])
    try:
        module.synthesize_fixes_for_findings([finding], object(), {"head": {"sha": "abc"}}, {}, SimpleNamespace(), reporter)
    except FakeReviewQualityError:
        pass
    else:
        raise AssertionError("live no-code-modification contradiction must fail closed")


def test_weak_no_repair_wording_does_not_override_concrete_repair() -> None:
    finding = {
        "path": "tools/example.py",
        "line": 7,
        "title": "Bound the caller-provided limit",
        "body": "The caller can request an unbounded result set.",
        "suggested_replacement": "limit = min(limit, 100)",
        "fix_guidance": {
            "language": "python",
            "notes": "No additional code modification is required after applying this exact replacement.",
        },
    }
    assert precision_guard.fix_synthesis_self_disqualification_reason(finding) == ""


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
    assert precision_guard.fix_synthesis_self_disqualification_reason(finding) == ""
    module, hardened, reporter = _module_returning([finding])
    result = module.synthesize_fixes_for_findings([finding], object(), {"head": {"sha": "abc"}}, {}, SimpleNamespace(), reporter)
    assert result[0]["title"] == finding["title"]
    artifact = hardened.artifacts[precision_guard.OUTCOME_ARTIFACT]
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
    artifact = hardened.artifacts[precision_guard.OUTCOME_ARTIFACT]
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
    assert precision_guard.fix_synthesis_self_disqualification_reason(finding) == ""


def test_legacy_artifact_contract_is_preserved() -> None:
    assert precision_guard.OUTCOME_ARTIFACT == "metadata/fix-synthesis-outcomes-v19.json"
    assert precision_guard.ARTIFACT_SCHEMA_VERSION == "v19"


def test_explicit_precision_stages_do_not_replace_shared_callables() -> None:
    source = Path(".github/dcoir_review/scripts/dcoir_review/precision_guard.py").read_text(encoding="utf-8")
    assert "_dcoir_precision_guard_original" not in source
    assert ".detect_risk_sentinels =" not in source
    assert ".synthesize_fixes_for_findings =" not in source


def test_stable_owner_composition() -> None:
    from dcoir_review.entrypoint import DcoirReviewEntrypoint

    names = DcoirReviewEntrypoint().patch_module_names
    assert "dcoir_review.precision_guard" in names, names
    assert "dcoir_review_required_runtime_patch_v19" not in names, names
    index = names.index("dcoir_review.precision_guard")
    assert names[index - 1] == "dcoir_review_required_runtime_patch_v18", names[max(0, index - 2):index + 4]
    assert names[index + 1] == "dcoir_review_required_runtime_patch_v20", names[max(0, index - 2):index + 4]



def main() -> None:
    test_legacy_artifact_contract_is_preserved()
    test_stable_owner_composition()
    test_explicit_precision_stages_do_not_replace_shared_callables()
    test_language_scoped_sentinel_filter_suppresses_cross_language_fixture_text()
    test_fix_synthesis_false_positive_contradiction_fails_closed()
    test_live_no_code_modification_wording_fails_closed()
    test_weak_no_repair_wording_does_not_override_concrete_repair()
    test_normal_fix_guidance_is_not_self_disqualifying()
    test_safe_native_suggestion_is_recorded_and_renders_github_suggestion_fence()
    test_detector_text_alone_cannot_self_disqualify_after_synthesis()
    print("dcoir_review_precision_guard_selftest passed")


if __name__ == "__main__":
    main()
