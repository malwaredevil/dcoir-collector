"""Report rendering for the Gemini production-like harness validator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_summary(
    messages: list[dict[str, str]],
    blind_report: dict[str, Any],
    collector_report: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    errors = [message for message in messages if message["level"] == "error"]
    warnings = [message for message in messages if message["level"] == "warning"]
    return {
        "workflow_verdict": "success" if not errors else "failure",
        "harness_success": str(not errors).lower(),
        "behavior_success": "not_scored_static_harness",
        "evidence_fidelity": "static" if mode == "light" else "static_plus_construct_build",
        "mode": mode,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "legacy_matrix_count": blind_report.get("legacy_matrix_count", 0),
        "scenario_count": blind_report.get("scenario_count", 0),
        "collector_fixture_count": collector_report.get("fixture_count", 0),
    }


def write_reports(output_dir: Path, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gemini_production_like_harness_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    (output_dir / "gemini_production_like_scenario_matrix.json").write_text(
        json.dumps(
            {
                "summary": report["summary"],
                "scenarios": report["blind_scenarios"].get("prompts", []),
                "collector_fixtures": report.get("collector_fixtures", {}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown = ["# Gemini Production-Like Behavioral Harness Report", "", "## Summary"]
    markdown += [f"- {key}: `{value}`" for key, value in report["summary"].items()]
    markdown += [
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Owner | Family | Tier | Attachments | Expected verdict |",
        "|---|---|---|---|---:|---|",
    ]
    for row in report["blind_scenarios"].get("prompts", []):
        markdown.append(
            f"| {row['scenario_id']} | {row['owner']} | {row['family']} | "
            f"{row['tier']} | {row['attachment_count']} | {row['expected_verdict']} |"
        )

    markdown += [""]
    markdown += ["## Messages"]
    markdown += [
        f"- {message['level']}: {message['message']}"
        + (f" (`{message['path']}`)" if message.get("path") else "")
        for message in report["messages"]
    ]
    markdown += [
        "",
        "## Verdict Semantics",
        "",
        "- Workflow success means the harness ran and produced trustworthy evidence artifacts.",
        "- Harness success means schemas, prompt separation, artifact signals, redaction checks, and construct loading passed.",
        "- Behavior success remains `not_scored_static_harness` unless a deterministic or live model response lane is executed.",
        "- Raw collector bundles remain operator-supplied and ignored; committed sanitized fixture trees may be used for static/full-artifact harness coverage.",
    ]
    text = "\n".join(markdown) + "\n"
    (output_dir / "gemini_production_like_harness_report.md").write_text(text, encoding="utf-8")
    (output_dir / "chatgpt_workflow_report_section.md").write_text(text, encoding="utf-8")
