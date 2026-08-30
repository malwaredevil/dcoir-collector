#!/usr/bin/env python3
"""Run the deterministic Gemini behavioral replay validation suite."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib.gemini_behavioral_replay_selection import resolve_fixtures

SUPPORT = Path("project_sources/gemini/fixtures/behavioral_replay/supporting_artifacts")

KNOWN_GOOD = [
    (
        "dcoir_operator_state_first_issue_124",
        SUPPORT / "dcoir_operator_state_first_issue_124_known_good_response_pack.json",
        "run_good_issue_124",
    ),
    (
        "dcoir_byovd_evidence_discipline_issue_122",
        SUPPORT / "dcoir_byovd_evidence_discipline_issue_122_known_good_response_pack.json",
        "run_good_issue_122",
    ),
    (
        "dcoir_long_transcript_continuity_issue_123",
        SUPPORT / "dcoir_long_transcript_continuity_issue_123_known_good_response_pack.json",
        "run_good_issue_123",
    ),
    (
        "dcoir_kql_unique_value_miss_issue_174",
        SUPPORT / "dcoir_kql_unique_value_miss_issue_174_known_good_response_pack.json",
        "run_good_issue_174",
    ),
]

KNOWN_BAD = [
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_response_pack.json", "Issue 122 baseline"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_negated_required_response_pack.json", "Issue 122 negated-required"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_post_rejection_response_pack.json", "Issue 122 post-marker rejection"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_connector_rejection_response_pack.json", "Issue 122 connector rejection"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_modifier_rejection_response_pack.json", "Issue 122 modifier rejection"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_quoted_marker_response_pack.json", "Issue 122 quoted marker"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_question_reversal_response_pack.json", "Issue 122 question reversal"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_wrong_to_treat_response_pack.json", "Issue 122 wrong-to-treat"),
    ("dcoir_byovd_evidence_discipline_issue_122", "dcoir_byovd_evidence_discipline_issue_122_known_bad_not_enough_to_say_response_pack.json", "Issue 122 not-enough-to-say"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_response_pack.json", "Issue 123 baseline"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_negated_required_response_pack.json", "Issue 123 negated-required"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_article_negation_response_pack.json", "Issue 123 article negation"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_request_rejection_response_pack.json", "Issue 123 request rejection"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_should_not_request_response_pack.json", "Issue 123 should-not-request"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_quoted_marker_response_pack.json", "Issue 123 quoted marker"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_suffix_response_pack.json", "Issue 123 suffix marker"),
    ("dcoir_long_transcript_continuity_issue_123", "dcoir_long_transcript_continuity_issue_123_known_bad_not_needed_response_pack.json", "Issue 123 not-needed"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_absence_response_pack.json", "Issue 174 miss-to-absence"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_malicious_response_pack.json", "Issue 174 miss-to-malicious"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_benign_response_pack.json", "Issue 174 miss-to-benign"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_repeat_shape_response_pack.json", "Issue 174 repeat-shape"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_broad_spam_response_pack.json", "Issue 174 broad-spam"),
    ("dcoir_kql_unique_value_miss_issue_174", "dcoir_kql_unique_value_miss_issue_174_known_bad_invented_search_response_pack.json", "Issue 174 invented-search"),
]

AGENT_DESIGNER_CAPTURE_GOOD = [
    (
        "dcoir_agent_designer_visible_writer_issue_398",
        "dcoir_agent_designer_visible_writer_issue_398_known_good_capture.json",
        "Issue 398 visible-writer good capture",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_good_capture.json",
        "Issue 398 collector-procedure good capture",
    ),
]

AGENT_DESIGNER_CAPTURE_BAD = [
    (
        "dcoir_agent_designer_visible_writer_issue_398",
        "dcoir_agent_designer_visible_writer_issue_398_known_bad_capture.json",
        "Issue 398 visible-writer bad capture",
    ),
    (
        "dcoir_agent_designer_visible_writer_issue_398",
        "dcoir_agent_designer_visible_writer_issue_398_known_bad_duplicate_only_capture.json",
        "Issue 398 visible-writer duplicate-only control",
    ),
    (
        "dcoir_agent_designer_visible_writer_issue_398",
        "dcoir_agent_designer_visible_writer_issue_398_known_bad_negated_routing_capture.json",
        "Issue 398 visible-writer negated-routing-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_capture.json",
        "Issue 398 collector-procedure bad capture",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_missing_stage_capture.json",
        "Issue 398 collector missing-stage-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_lane_separation_capture.json",
        "Issue 398 collector lane-separation-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_negated_lane_separation_capture.json",
        "Issue 398 collector negated-lane-separation-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_vague_summary_capture.json",
        "Issue 398 collector vague-summary-only control",
    ),
]

ISSUE_398_AGENT_DESIGNER_FIXTURES = {
    "dcoir_agent_designer_visible_writer_issue_398",
    "dcoir_agent_designer_collector_procedure_issue_398",
}


def safe_label(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in label)


def run(args: list[str], *, stdout: Path | None = None, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    if stdout is None:
        result = subprocess.run(args, text=True, check=False)
    else:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        with stdout.open("w", encoding="utf-8") as fh:
            result = subprocess.run(args, text=True, stdout=fh, check=False)
    if expect_success and result.returncode != 0:
        raise SystemExit(result.returncode)
    if not expect_success and result.returncode == 0:
        raise SystemExit("Command unexpectedly succeeded: " + " ".join(args))
    return result


def run_known_good(fixtures_root: Path, output_dir: Path) -> None:
    for fixture_id, response_pack, output_name in KNOWN_GOOD:
        run(
            [
                sys.executable,
                "project_sources/gemini/tools/run_gemini_behavioral_replay.py",
                "--fixtures-root",
                str(fixtures_root),
                "--fixture-id",
                fixture_id,
                "--response-pack",
                str(response_pack),
                "--output-dir",
                str(output_dir / output_name),
            ]
        )


def run_known_bad(fixtures_root: Path, output_dir: Path) -> None:
    bad_dir = output_dir / "known_bad_results"
    bad_dir.mkdir(parents=True, exist_ok=True)
    for fixture_id, response_pack_name, label in KNOWN_BAD:
        output = bad_dir / f"{safe_label(label)}.json"
        result = run(
            [
                sys.executable,
                "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                "--fixtures-root",
                str(fixtures_root),
                "--response-pack",
                str(SUPPORT / response_pack_name),
                "--fixture-id",
                fixture_id,
            ],
            stdout=output,
            expect_success=False,
        )
        if result.returncode == 0:
            print(output.read_text(encoding="utf-8", errors="replace"))
            raise SystemExit(f"{label} known-bad response pack unexpectedly passed.")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("success") is not False:
            raise SystemExit(f"Known-bad report did not contain success=false: {output}")


def assert_isolated_control_reason(label: str, payload: dict) -> None:
    result = payload.get("result") or {}
    rows = result.get("per_turn") or []
    if len(rows) != 1:
        raise SystemExit(f"{label} expected exactly one scored turn, found {len(rows)}")
    row = rows[0]
    required = row.get("required_markers") or {}
    forbidden = row.get("forbidden_markers") or {}
    anomaly_types = [str(item.get("type")) for item in (row.get("anomalies") or [])]

    if "duplicate-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["duplicate_final_sections"]:
            raise SystemExit(f"{label} did not fail solely on duplicate_final_sections: {json.dumps(row, sort_keys=True)}")
    elif "negated-routing-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 1 or forbidden.get("literal_hits") != ["routing to"] or anomaly_types:
            raise SystemExit(f"{label} did not fail solely on literal negated routing leakage: {json.dumps(row, sort_keys=True)}")
    elif "missing-stage-only" in label:
        if required.get("missing") != ["interpret"] or required.get("ratio") != 0.8 or forbidden.get("count") != 0 or anomaly_types:
            raise SystemExit(f"{label} did not fail solely on the missing interpret lifecycle stage: {json.dumps(row, sort_keys=True)}")
    elif "negated-lane-separation-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["missing_execution_lane_separation"]:
            raise SystemExit(f"{label} did not fail solely on negated lane separation: {json.dumps(row, sort_keys=True)}")
    elif "lane-separation-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["missing_execution_lane_separation"]:
            raise SystemExit(f"{label} did not fail solely on missing_execution_lane_separation: {json.dumps(row, sort_keys=True)}")
    elif "vague-summary-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["incomplete_collector_procedure_actionability"]:
            raise SystemExit(f"{label} did not fail solely on incomplete collector procedure actionability: {json.dumps(row, sort_keys=True)}")


def _selection_args(mode: str, *, custom_fixture: str = "", run_all: bool = True) -> argparse.Namespace:
    return argparse.Namespace(
        mode=mode,
        fixture_ids_csv=None,
        fixture_id=None,
        custom_fixtures_csv=custom_fixture,
        run_all_active_fixtures=run_all,
    )


def run_fixture_mode_selection_selftests(fixtures_root: Path) -> None:
    script_path = Path("project_sources/gemini/tools/run_gemini_behavioral_replay.py").resolve()

    deterministic, deterministic_meta = resolve_fixtures(
        _selection_args("deterministic"), fixtures_root, script_path
    )
    deterministic_ids = {row["fixture"].get("fixture_id") for row in deterministic}
    if not ISSUE_398_AGENT_DESIGNER_FIXTURES.issubset(deterministic_ids):
        raise SystemExit("Issue #398 Agent Designer fixtures must remain deterministic-scorer eligible.")
    if deterministic_meta.get("required_fixture_mode") != "deterministic":
        raise SystemExit("Deterministic fixture-mode mapping is incorrect.")

    for mode, expected_fixture_mode in (("live", "live_gemini"), ("fallback", "fallback_emulation")):
        selected, metadata = resolve_fixtures(_selection_args(mode), fixtures_root, script_path)
        selected_ids = {row["fixture"].get("fixture_id") for row in selected}
        if ISSUE_398_AGENT_DESIGNER_FIXTURES.intersection(selected_ids):
            raise SystemExit(f"Agent Designer-only fixtures leaked into {mode} replay selection.")
        if not ISSUE_398_AGENT_DESIGNER_FIXTURES.issubset(set(metadata.get("excluded_from_mode") or [])):
            raise SystemExit(f"Agent Designer-only fixtures were not reported as mode-ineligible for {mode}.")
        if metadata.get("required_fixture_mode") != expected_fixture_mode:
            raise SystemExit(f"Runner mode {mode} mapped to the wrong fixture mode support value.")

    _, live_metadata = resolve_fixtures(_selection_args("live"), fixtures_root, script_path)
    if not ISSUE_398_AGENT_DESIGNER_FIXTURES.issubset(set(live_metadata.get("excluded_from_live_api") or [])):
        raise SystemExit("Agent Designer-only fixtures must remain explicitly excluded from raw live API replay.")

    _, fallback_custom = resolve_fixtures(
        _selection_args(
            "fallback",
            custom_fixture="dcoir_agent_designer_visible_writer_issue_398",
            run_all=False,
        ),
        fixtures_root,
        script_path,
    )
    rejected = fallback_custom.get("rejected_selected_fixtures") or []
    if len(rejected) != 1:
        raise SystemExit("Explicit fallback selection must produce exactly one rejection.")
    fallback_reason = str(rejected[0].get("reason", ""))
    if "fallback_emulation" not in fallback_reason:
        raise SystemExit("Explicit fallback rejection must identify fallback_emulation as the unsupported fixture mode.")


def run_agent_designer_capture_selftests(fixtures_root: Path, output_dir: Path) -> None:
    capture_dir = output_dir / "agent_designer_capture_results"
    capture_dir.mkdir(parents=True, exist_ok=True)
    for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_GOOD:
        output = capture_dir / f"{safe_label(label)}.json"
        run(
            [
                sys.executable,
                "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                "--fixtures-root",
                str(fixtures_root),
                "--response-pack",
                str(SUPPORT / response_pack_name),
                "--fixture-id",
                fixture_id,
                "--expected-mode",
                "agent_designer_capture",
            ],
            stdout=output,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("success") is not True:
            raise SystemExit(f"Known-good Agent Designer capture did not contain success=true: {output}")
    for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_BAD:
        output = capture_dir / f"{safe_label(label)}.json"
        run(
            [
                sys.executable,
                "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                "--fixtures-root",
                str(fixtures_root),
                "--response-pack",
                str(SUPPORT / response_pack_name),
                "--fixture-id",
                fixture_id,
                "--expected-mode",
                "agent_designer_capture",
            ],
            stdout=output,
            expect_success=False,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("success") is not False:
            raise SystemExit(f"Known-bad Agent Designer capture did not contain success=false: {output}")
        assert_isolated_control_reason(label, payload)


def run_mode_mismatch(fixtures_root: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
            "--fixtures-root",
            str(fixtures_root),
            "--response-pack",
            str(SUPPORT / "dcoir_byovd_evidence_discipline_issue_122_known_good_response_pack.json"),
            "--fixture-id",
            "dcoir_byovd_evidence_discipline_issue_122",
            "--expected-mode",
            "live_gemini",
        ],
        check=False,
    )
    if result.returncode == 0:
        raise SystemExit("Deterministic response pack unexpectedly passed a live_gemini expected-mode check.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures-root", type=Path, default=Path("project_sources/gemini/fixtures/behavioral_replay"))
    parser.add_argument("--output-dir", type=Path, default=Path("project_sources/validation/out_validate_gemini_behavioral_replay"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "project_sources/gemini/tools/validate_gemini_behavioral_replay_fixtures.py",
            "--fixtures-root",
            str(args.fixtures_root),
            "--output-dir",
            str(args.output_dir / "fixtures"),
        ]
    )
    run_fixture_mode_selection_selftests(args.fixtures_root)
    run_known_good(args.fixtures_root, args.output_dir)
    run(
        [
            sys.executable,
            "project_sources/gemini/tools/render_gemini_behavioral_replay_report.py",
            "--results-json",
            str(args.output_dir / "run_good_issue_124" / "gemini_behavioral_replay_run_report.json"),
            "--output-path",
            str(args.output_dir / "run_good_issue_124" / "gemini_behavioral_replay_rendered_report.md"),
        ]
    )
    run_known_bad(args.fixtures_root, args.output_dir)
    run_agent_designer_capture_selftests(args.fixtures_root, args.output_dir)
    run_mode_mismatch(args.fixtures_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
