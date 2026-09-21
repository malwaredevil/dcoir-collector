from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

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


def _approved_capture_output_root(output_dir: Path) -> Path:
    candidate = output_dir.resolve()
    roots = (Path("project_sources/validation").resolve(), Path(tempfile.gettempdir()).resolve())
    if not any(candidate == root or candidate.is_relative_to(root) for root in roots):
        raise SystemExit(f"Bad: {candidate}")
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _bounded_capture_path(governed_root: Path, candidate: Path) -> Path:
    root = governed_root.resolve()
    resolved = candidate.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise SystemExit(f"Escape: {resolved}")
    return resolved


def _run(
    args: list[str],
    *,
    stdout: Path,
    governed_root: Path,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    safe_stdout = _bounded_capture_path(governed_root, stdout)
    safe_stdout.parent.mkdir(parents=True, exist_ok=True)
    with safe_stdout.open("w", encoding="utf-8") as fh:
        result = subprocess.run(args, text=True, stdout=fh, check=False)  # nosec B603
    if expect_success and result.returncode != 0:
        raise SystemExit(result.returncode)
    if not expect_success and result.returncode == 0:
        raise SystemExit("Command unexpectedly succeeded: " + " ".join(args))
    return result


def _write_capture_mode_variant(
    source: Path,
    destination: Path,
    mode: str,
    model_name: str,
    *,
    governed_root: Path,
) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["mode"] = mode
    payload["model_name"] = model_name
    metadata = dict(payload.get("metadata") or {})
    metadata["capture_surface"] = mode
    payload["metadata"] = metadata
    safe_destination = _bounded_capture_path(governed_root, destination)
    safe_destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_openai_webui_capture_selftests(fixtures_root: Path, output_dir: Path, support: Path) -> None:
    governed_root = _approved_capture_output_root(output_dir)
    capture_dir = _bounded_capture_path(governed_root, governed_root / "openai_webui_capture_results")
    capture_dir.mkdir(parents=True, exist_ok=True)
    for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_GOOD:
        variant = capture_dir / f"{_safe_label(label)}_input.json"
        output = capture_dir / f"{_safe_label(label)}.json"
        _write_capture_mode_variant(
            support / response_pack_name,
            variant,
            "openai_webui_capture",
            "GPT-5.6 Terra",
            governed_root=governed_root,
        )
        _run(
            [
                sys.executable,
                "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                "--fixtures-root", str(fixtures_root),
                "--response-pack", str(variant),
                "--fixture-id", fixture_id,
                "--expected-mode", "openai_webui_capture",
            ],
            stdout=output,
            governed_root=governed_root,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("success") is not True:
            raise SystemExit(f"Known-good OpenAI WebUI capture did not contain success=true: {output}")
    for fixture_id, response_pack_name, label in AGENT_DESIGNER_CAPTURE_BAD:
        variant = capture_dir / f"{_safe_label(label)}_input.json"
        output = capture_dir / f"{_safe_label(label)}.json"
        _write_capture_mode_variant(
            support / response_pack_name,
            variant,
            "openai_webui_capture",
            "GPT-5.6 Terra",
            governed_root=governed_root,
        )
        _run(
            [
                sys.executable,
                "project_sources/gemini/tools/score_gemini_behavioral_replay.py",
                "--fixtures-root", str(fixtures_root),
                "--response-pack", str(variant),
                "--fixture-id", fixture_id,
                "--expected-mode", "openai_webui_capture",
            ],
            stdout=output,
            governed_root=governed_root,
            expect_success=False,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("success") is not False:
            raise SystemExit(f"Known-bad OpenAI WebUI capture did not contain success=false: {output}")
        assert_isolated_control_reason(label, payload)
