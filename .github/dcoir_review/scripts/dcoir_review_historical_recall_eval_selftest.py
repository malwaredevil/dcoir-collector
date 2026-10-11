#!/usr/bin/env python3
"""No-network review comparator tests grounded in the actual PR #617 commits."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import dcoir_review_cross_file_recall_eval as evaluation
import dcoir_review_historical_recall_cases as history


def _response(findings: list[dict]) -> dict:
    return {"ok": True, "result": {"findings": findings, "summary": "bounded offline test"}}


def main() -> None:
    cases = history.cases()
    assert [row["id"] for row in cases] == [history.ORIGINAL_CASE, history.SAFE_CASE]
    assert len(evaluation.load_cases()) == 6, "Existing synthetic comparison must remain unchanged"
    config = evaluation.review.load_pareto_context_config(
        str(evaluation.DCOIR_ROOT / "openrouter-pr-review-pareto.yml")
    )
    positive, safe = cases
    assert positive["reviewed_head"] == history.BAD_SHA
    assert safe["reviewed_head"] == history.SAFE_SHA
    assert positive["expected"] == "finding" and safe["expected"] == "clean"
    assert "verify_powershell_surface_inventory_ci.py" not in positive["focus_source"]
    assert "verify_powershell_surface_inventory_ci.py" in safe["focus_source"]
    assert "verify_powershell_surface_inventory_ci.py" in safe["changed_diff"]
    assert "PowerShell source inventory is stale" in safe["changed_diff"]
    assert "git ls-files -z" in safe["dependency_sources"][history.VERIFIER]
    assert len(evaluation.mutation.added_lines(evaluation.focus_patch(positive))) >= 1
    assert len(evaluation.mutation.added_lines(evaluation.focus_patch(safe))) >= 1

    before = evaluation.prompts(positive, config)
    after = evaluation.prompts(safe, config)
    for pair in (before, after):
        assert pair["baseline"] != pair["enhanced"]
        assert "Exact-reviewed-head dependency evidence" not in pair["baseline"]
        assert "Exact-reviewed-head dependency evidence" in pair["enhanced"]
        assert len(pair["baseline"]) <= config.max_prompt_chars
        assert len(pair["enhanced"]) <= config.max_prompt_chars
        for prompt in pair.values():
            assert "HIDDEN_TRUTH_NEVER_APPEARS_IN_MODEL_PROMPTS" not in prompt
            assert "HIDDEN_COUNTEREXAMPLE_NEVER_APPEARS_IN_MODEL_PROMPTS" not in prompt
    assert "Cross-file contract review cues" in before["enhanced"]
    assert "for surface in inventory" in before["enhanced"]
    assert "inventory = load_inventory(" in before["enhanced"]
    assert "verify_powershell_surface_inventory_ci.py" in after["enhanced"]
    assert "git ls-files -z" in after["enhanced"]
    assert "verify_powershell_analyzer_policy_ci.py" in before["enhanced"]
    assert "verify_powershell_analyzer_policy_ci.py" in after["enhanced"]

    # The P1 scoring target is the actual newly added right-side action line.
    anchor = next(line for line, text in evaluation.mutation.added_lines(evaluation.focus_patch(positive))
                  if positive["expected_anchor"] in text)
    finding = {
        "path": positive["focus_path"], "line": anchor, "severity": "high",
        "title": "Newly tracked PowerShell source omission",
        "body": "The inventory enumerator can omit Git-tracked files, allowing the analyzer to skip coverage checks",
        "validation": "Create a new tracked PowerShell source absent from inventory and verify the gate fails",
    }
    perfect = evaluation.score(positive, _response([finding]))
    assert perfect["root_cause_detected"] and perfect["severity_aligned"] and perfect["correct"]
    understated = evaluation.score(positive, _response([{**finding, "severity": "medium"}]))
    assert understated["root_cause_detected"] and not understated["severity_aligned"]
    assert understated["disposition"] == "severity-understated"
    assert evaluation.score(positive, _response([]))["disposition"] == "false-negative"
    assert not evaluation.score(positive, _response([{**finding, "line": 999}]))["root_cause_detected"]
    unrelated = {**finding, "body": "Consider formatting this diff", "title": "Style only", "validation": "run style checks"}
    assert not evaluation.score(positive, _response([unrelated]))["root_cause_detected"]
    assert evaluation.score(safe, _response([]))["correct"]
    assert evaluation.score(safe, _response([finding]))["disposition"] == "false-positive"

    # Adva: a missing exact-HEAD *direct verifier* must block the safe
    # comparison even when the analyzer and inventory helper are available.
    broken = dict(safe)
    broken["dependency_sources"] = dict(safe["dependency_sources"])
    broken["dependency_sources"].pop(history.VERIFIER)
    try:
        evaluation.prompts(broken, config)
    except RuntimeError as exc:
        assert "exact-head executable dependency unavailable" in str(exc)
    else:
        raise AssertionError("Absent safety verifier was omitted without a failure")

    # Opposite-polarity caller check: the earlier action also invokes a
    # policy verifier. Omitting it must not silently downgrade to a clean pass.
    broken_original = dict(positive)
    broken_original["dependency_sources"] = dict(positive["dependency_sources"])
    broken_original["dependency_sources"].pop(
        "project_sources/collector/tools/verify_powershell_analyzer_policy_ci.py"
    )
    try:
        evaluation.prompts(broken_original, config)
    except RuntimeError as exc:
        assert "exact-head executable dependency unavailable" in str(exc)
    else:
        raise AssertionError("Omitted original direct policy verifier was accepted")

    # No paid key, no OpenRouter calls. Existing invocation syntax supports
    # historical ids through --case while the unselected default stays 6 cases.
    with patch.object(evaluation.base, "call_openrouter", side_effect=AssertionError("network forbidden")):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "historical-plan.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = evaluation.main([
                    "--candidate", "sonnet5.5-high", "--case", history.ORIGINAL_CASE,
                    "--case", history.SAFE_CASE, "--max-requests", "4",
                    "--output", str(report_path),
                ])
            assert code == 0
            report = json.loads(report_path.read_text(encoding="utf-8"))
            assert report["mode"] == "plan" and report["planned_requests"] == 4
            assert report["evidence_population"] == "historical-source-backed"
            assert "not a statistical recall estimate" in report["interpretation_limit"]
            assert report["network_requests_made"] == 0 and not report["results"]
            assert [item["case_id"] for item in report["cases"]] == [history.ORIGINAL_CASE, history.SAFE_CASE]
            assert all(item["prompts"]["baseline"]["sha256"] != item["prompts"]["enhanced"]["sha256"]
                       for item in report["cases"])
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    evaluation.main(["--candidate", "sonnet5.5-high",
                                     "--case", history.ORIGINAL_CASE,
                                     "--case", history.SAFE_CASE, "--max-requests", "3"])
            except SystemExit as exc:
                assert "beyond --max-requests" in str(exc)
            else:
                raise AssertionError("The request budget did not fail closed")

    print("PASS: real original/repaired PR617 source comparison, 4 planned, 0 network calls")
    print("PASS: P1 vs severity, false-positive safe case, missing direct verifier, request cap")


if __name__ == "__main__":
    main()
