#!/usr/bin/env python3
"""Run the deterministic Gemini behavioral replay validation suite."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

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
    run_mode_mismatch(args.fixtures_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
