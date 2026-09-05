#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import dcoir_review_pr_mutation_eval as target


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def finding(title: str, body: str, path: str, line: int, validation: str = "validate") -> dict:
    return {
        "title": title,
        "body": body,
        "validation": validation,
        "path": path,
        "line": line,
        "severity": "high",
        "confidence": 0.99,
        "suggested_replacement": "",
    }


def added_line(case: dict, path: str, contains: str) -> int:
    for item in case["files"]:
        if item["filename"] != path:
            continue
        for line, text in target.added_lines(item["patch"]):
            if contains in text:
                return line
    raise AssertionError(f"No added line containing {contains!r} in {path}")


def main() -> int:
    cases = target.load_cases()
    require(len(cases) == 12, "expected 12 PR mutation cases")
    require(sum(len(case["expected_findings"]) for case in cases) == 10, "expected 10 seeded findings")
    require(sum(not case["expected_findings"] for case in cases) == 4, "expected 4 clean PR controls")

    for case in cases:
        prompt = target.build_pr_prompt(case)
        lower = prompt.lower()
        require("ground_truth_rationale" not in lower, f"ground-truth key leaked for {case['id']}")
        require("expected_findings" not in lower, f"expected-findings key leaked for {case['id']}")
        require("defect_class" not in lower, f"defect-class key leaked for {case['id']}")
        require("allowed_paths" not in lower, f"allowed-path key leaked for {case['id']}")
        require("Changed file summary:" in prompt and "Unified diff:" in prompt, "production prompt shape missing")

    hidden = {
        "id": "sentinel",
        "pr_title": "Title",
        "pr_body": "Body",
        "difficulty": "SECRET_DIFFICULTY_SENTINEL",
        "ground_truth_rationale": "SECRET_GROUND_TRUTH_SENTINEL",
        "expected_findings": [],
        "files": [{
            "filename": "x.py",
            "status": "modified",
            "patch": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n",
        }],
    }
    prompt = target.build_pr_prompt(hidden)
    require("SECRET_DIFFICULTY_SENTINEL" not in prompt, "difficulty sentinel leaked")
    require("SECRET_GROUND_TRUTH_SENTINEL" not in prompt, "ground-truth sentinel leaked")

    clean_case = next(case for case in cases if case["id"] == "prmut-ps-clean-native-exit")
    require(target.score_case(clean_case, {"ok": True, "result": {"findings": []}})["correct"], "clean scoring failed")

    defect_case = next(case for case in cases if case["id"] == "prmut-ps-native-exit-overwrite")
    good = finding(
        "Snapshot robocopy exit code before where.exe overwrites LASTEXITCODE",
        "The second native where.exe call overwrites the robocopy exit code. Snapshot it first.",
        "src/Invoke-Mirror.ps1",
        added_line(defect_case, "src/Invoke-Mirror.ps1", "where.exe powershell.exe"),
        "Exercise a failing robocopy exit code.",
    )
    score = target.score_case(defect_case, {"ok": True, "result": {"findings": [good]}})
    require(score["correct"] and score["detected_findings"] == 1, f"expected finding was not credited: {score}")

    companion = finding(
        "Add a regression for the overwritten robocopy exit code",
        "This changed test should exercise that where.exe overwrites LASTEXITCODE after robocopy unless the native exit code is snapshotted.",
        "tests/Invoke-Mirror.Tests.ps1",
        added_line(defect_case, "tests/Invoke-Mirror.Tests.ps1", "collects diagnostic tool location"),
    )
    companion_score = target.score_case(defect_case, {"ok": True, "result": {"findings": [good, companion]}})
    require(companion_score["correct"], f"root-cause companion finding should not become a false positive: {companion_score}")
    require(companion_score["supported_companion_findings"] == 1, "companion finding was not classified separately")
    require(companion_score["extra_findings"] == 0, "companion finding leaked into extras")

    unrelated = finding("Style cleanup", "Unrelated formatting preference.", "src/Invoke-Mirror.ps1", added_line(defect_case, "src/Invoke-Mirror.ps1", "where.exe powershell.exe"), "none")
    require(not target.score_case(defect_case, {"ok": True, "result": {"findings": [unrelated]}})["correct"], "unrelated finding received credit")

    clean_noise = finding("Style cleanup", "Unrelated formatting preference.", "src/Invoke-Mirror.ps1", added_line(clean_case, "src/Invoke-Mirror.ps1", "where.exe powershell.exe"), "none")
    clean_noise_score = target.score_case(clean_case, {"ok": True, "result": {"findings": [clean_noise]}})
    require(not clean_noise_score["correct"] and clean_noise_score["extra_findings"] == 1, "clean controls must remain strict")

    multi = next(case for case in cases if case["id"] == "prmut-mixed-stale-head-and-concurrency")
    cross_file_root = finding(
        "Concurrency does not replace the stale-head publication guard",
        "Removing the current head refetch allows stale publication, and cancel-in-progress false means a superseded concurrency run can still finish after a newer head. Restore the pre-publication current-head check and cancel obsolete runs.",
        "review/publish.py",
        added_line(multi, "review/publish.py", "workflow concurrency group prevents overlapping reviews"),
        "Advance the PR head while a review runs and verify the stale run neither publishes nor survives the newer run.",
    )
    multi_score = target.score_case(multi, {"ok": True, "result": {"findings": [cross_file_root]}})
    require(multi_score["correct"], f"one focused cross-file root-cause finding should satisfy both seeded facets: {multi_score}")
    require(multi_score["detected_findings"] == 2, "cross-file finding did not satisfy both seeded facets")
    require(multi_score["extra_findings"] == 0, "cross-file root finding was counted as extra")

    doc_drift = next(case for case in cases if case["id"] == "prmut-mixed-remoting-and-doc-drift")
    alternative_anchor = finding(
        "Debug documentation contradicts the mode resolver",
        "The documentation says debug is observability-only, but the changed resolver maps debug to deep and changes review scope.",
        "docs/operator.md",
        added_line(doc_drift, "docs/operator.md", "Debug mode only adds diagnostics"),
    )
    second_target = doc_drift["expected_findings"][1]
    require(target.finding_matches(doc_drift, second_target, alternative_anchor), "allowed alternative anchor did not match the seeded facet")

    original = target.base.call_openrouter
    try:
        target.base.call_openrouter = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called in plan mode"))
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "plan.json"
            rc = target.main(["--candidate", "sonnet5-high", "--output", str(output)])
            require(rc == 0, "plan mode failed")
            report = json.loads(output.read_text(encoding="utf-8"))
            require(report["network_requests_made"] == 0, "plan mode reported network traffic")
            require(report["planned_requests"] == 12, "unexpected plan request count")
            require(report["schema_version"] == "dcoir_review_pr_mutation_eval_report_v2", "unexpected report schema")
    finally:
        target.base.call_openrouter = original

    print("PASS: production-shaped PR mutation evaluator selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
