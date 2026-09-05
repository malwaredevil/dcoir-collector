#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import dcoir_review_pr_mutation_eval as target


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


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
    good = {
        "ok": True,
        "result": {
            "findings": [{
                "title": "Snapshot robocopy exit code before where.exe overwrites LASTEXITCODE",
                "body": "The second native where.exe call overwrites the robocopy exit code. Snapshot it first.",
                "validation": "Exercise a failing robocopy exit code.",
                "path": "src/Invoke-Mirror.ps1",
                "line": 4,
                "severity": "high",
                "confidence": 0.99,
                "suggested_replacement": "",
            }]
        },
    }
    score = target.score_case(defect_case, good)
    require(score["correct"] and score["detected_findings"] == 1, f"expected finding was not credited: {score}")

    unrelated = {
        "ok": True,
        "result": {
            "findings": [{
                "title": "Style cleanup",
                "body": "Unrelated formatting preference.",
                "validation": "none",
                "path": "src/Invoke-Mirror.ps1",
                "line": 4,
                "severity": "low",
                "confidence": 0.9,
                "suggested_replacement": "",
            }]
        },
    }
    require(not target.score_case(defect_case, unrelated)["correct"], "unrelated finding received credit")

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
    finally:
        target.base.call_openrouter = original

    print("PASS: production-shaped PR mutation evaluator selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
