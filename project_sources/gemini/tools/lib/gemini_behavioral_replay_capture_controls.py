from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from pathlib import Path

from .gemini_behavioral_replay_capture_adversarial import assert_private_capture_root
from .gemini_behavioral_replay_capture_paths import (
    PrivateCaptureRoot,
    allocate_private_capture_root,
    capture_process_path,
    cleanup_private_capture_root,
    open_capture_text_exclusive,
    read_capture_text,
)
from .gemini_behavioral_replay_selection import resolve_fixtures

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
        "dcoir_agent_designer_visible_writer_issue_398",
        "dcoir_agent_designer_visible_writer_issue_398_known_bad_internal_state_only_capture.json",
        "Issue 398 visible-writer internal-state-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_capture.json",
        "Issue 398 collector-procedure bad capture",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_duplicate_only_capture.json",
        "Issue 398 collector duplicate-only control",
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
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_negated_action_capture.json",
        "Issue 398 collector negated-action-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_mixed_wrapper_capture.json",
        "Issue 398 collector mixed-wrapper-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_retrieval_unavailable_capture.json",
        "Issue 398 collector retrieval-unavailable-only control",
    ),
    (
        "dcoir_agent_designer_collector_procedure_issue_398",
        "dcoir_agent_designer_collector_procedure_issue_398_known_bad_cleanup_prohibited_capture.json",
        "Issue 398 collector cleanup-prohibited-only control",
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
    elif "internal-state-only" in label:
        expected_hits = ["prime summary", "planner_payload", "routing_state"]
        if required.get("ratio") != 1.0 or forbidden.get("count") != 3 or forbidden.get("literal_hits") != expected_hits or anomaly_types:
            raise SystemExit(f"{label} did not fail solely on serialized internal-state leakage: {json.dumps(row, sort_keys=True)}")
    elif "missing-stage-only" in label:
        if required.get("missing") != ["interpret"] or required.get("ratio") != 0.8 or forbidden.get("count") != 0 or anomaly_types:
            raise SystemExit(f"{label} did not fail solely on the missing interpret lifecycle stage: {json.dumps(row, sort_keys=True)}")
    elif "negated-lane-separation-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["missing_execution_lane_separation"]:
            raise SystemExit(f"{label} did not fail solely on negated lane separation: {json.dumps(row, sort_keys=True)}")
    elif "lane-separation-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["missing_execution_lane_separation"]:
            raise SystemExit(f"{label} did not fail solely on missing_execution_lane_separation: {json.dumps(row, sort_keys=True)}")
    elif "negated-action-only" in label:
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["incomplete_collector_procedure_actionability"]:
            raise SystemExit(f"{label} did not fail solely on incomplete collector procedure actionability: {json.dumps(row, sort_keys=True)}")
    elif (
        "mixed-wrapper-only" in label
        or "retrieval-unavailable-only" in label
        or "cleanup-prohibited-only" in label
    ):
        if required.get("ratio") != 1.0 or forbidden.get("count") != 0 or anomaly_types != ["incomplete_collector_procedure_actionability"]:
            raise SystemExit(f"{label} did not fail solely on incomplete collector procedure actionability: {json.dumps(row, sort_keys=True)}")
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

def _safe_label(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in label)

def _run(
    args: list[str],
    *,
    stdout_name: str,
    private_root: PrivateCaptureRoot,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    with open_capture_text_exclusive(private_root, stdout_name) as fh:
        result = subprocess.run(
            args, text=True, stdout=fh, check=False, pass_fds=(private_root.dir_fd,)
        )  # nosec B603
    if expect_success and result.returncode:
        raise SystemExit(result.returncode)
    if not expect_success and not result.returncode:
        raise SystemExit("Unexpected pass: " + " ".join(args))
    return result

def _write_capture_mode_variant(
    source: Path,
    destination_name: str,
    mode: str,
    model_name: str,
    *,
    private_root: PrivateCaptureRoot,
) -> str:
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["mode"] = mode
    payload["model_name"] = model_name
    metadata = dict(payload.get("metadata") or {})
    metadata["capture_surface"] = mode
    payload["metadata"] = metadata
    with open_capture_text_exclusive(private_root, destination_name) as fh:
        fh.write(json.dumps(payload, indent=2) + "\n")
    return capture_process_path(private_root, destination_name)

def run_openai_webui_capture_selftests(fixtures_root: Path, output_dir: Path, support: Path) -> None:
    private_root = allocate_private_capture_root(output_dir)
    try:
        assert_private_capture_root(private_root)
        for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_GOOD:
            stem = _safe_label(label)
            variant = _write_capture_mode_variant(
                support / response_pack_name,
                f"{stem}_input.json",
                "openai_webui_capture",
                "GPT-5.6 Terra",
                private_root=private_root,
            )
            output_name = f"{stem}.json"
            output = output_name
            _run(
                [
                    sys.executable,
                    "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                    "--fixtures-root", str(fixtures_root),
                    "--response-pack", str(variant),
                    "--fixture-id", fixture_id,
                    "--expected-mode", "openai_webui_capture",
                ],
                stdout_name=output_name,
                private_root=private_root,
            )
            payload = json.loads(read_capture_text(private_root, output_name))
            if payload.get("success") is not True:
                raise SystemExit(f"Good failed: {output_name}")
        for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_BAD:
            stem = _safe_label(label)
            variant = _write_capture_mode_variant(
                support / response_pack_name,
                f"{stem}_input.json",
                "openai_webui_capture",
                "GPT-5.6 Terra",
                private_root=private_root,
            )
            output_name = f"{stem}.json"
            output = output_name
            _run(
                [
                    sys.executable,
                    "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                    "--fixtures-root", str(fixtures_root),
                    "--response-pack", str(variant),
                    "--fixture-id", fixture_id,
                    "--expected-mode", "openai_webui_capture",
                ],
                stdout_name=output_name,
                private_root=private_root,
                expect_success=False,
            )
            payload = json.loads(read_capture_text(private_root, output_name))
            if payload.get("success") is not False:
                raise SystemExit(f"Bad: {output_name}")
            assert_isolated_control_reason(label, payload)
    except BaseException as scoring_error:
        try:
            cleanup_private_capture_root(private_root)
        except BaseException as cleanup_error:
            raise scoring_error.with_traceback(scoring_error.__traceback__) from cleanup_error
        raise
    else:
        cleanup_private_capture_root(private_root)
