#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import lib.openai_dcoir_replay_live as replay_live

build_request_body = replay_live.build_request_body
extract_text = replay_live.extract_text
make_pack = replay_live.make_pack

from lib.gemini_behavioral_replay_runner import load_fixture_entry, load_fixture_index, repo_root_from_script
from lib.gemini_behavioral_replay_schema import validate_response_pack_shape
from lib.gemini_behavioral_replay_scoring import score_forbidden_markers, score_response_pack
from lib.gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps
from lib.gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from lib.gemini_behavioral_replay_selection import resolve_fixtures
from lib.openai_dcoir_replay_package import OPENAI_MODEL_ID, load_governed_openai_package
from lib.gemini_behavioral_replay_workflow_report import redact_report_value

FIXTURES_ROOT = Path("project_sources/gemini/fixtures/behavioral_replay")
SUPPORT = FIXTURES_ROOT / "supporting_artifacts"
GOOD_PACKS = {
    "dcoir_operator_state_first_issue_124": "dcoir_operator_state_first_issue_124_known_good_response_pack.json",
    "dcoir_byovd_evidence_discipline_issue_122": "dcoir_byovd_evidence_discipline_issue_122_known_good_response_pack.json",
    "dcoir_long_transcript_continuity_issue_123": "dcoir_long_transcript_continuity_issue_123_known_good_response_pack.json",
    "dcoir_kql_unique_value_miss_issue_174": "dcoir_kql_unique_value_miss_issue_174_known_good_response_pack.json",
    "dcoir_agent_designer_visible_writer_issue_398": "dcoir_agent_designer_visible_writer_issue_398_known_good_capture.json",
    "dcoir_agent_designer_collector_procedure_issue_398": "dcoir_agent_designer_collector_procedure_issue_398_known_good_capture.json",
}


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        mode="openai_live",
        fixture_ids_csv=None,
        fixture_id=None,
        custom_fixtures_csv="",
        run_all_active_fixtures=True,
        reasoning_effort="medium",
        max_output_tokens=8192,
        max_retries=1,
        retry_base_seconds=0.0,
        api_base="https://api.openai.com/v1/responses",
    )


def main() -> int:
    repo_root = repo_root_from_script(Path(__file__))
    package = load_governed_openai_package(repo_root)
    if package["model_id"] != OPENAI_MODEL_ID or len(package["knowledge_files"]) != 7:
        raise SystemExit("Governed Terra package identity or Knowledge count is incorrect.")

    args = _args()
    selected, meta = resolve_fixtures(args, FIXTURES_ROOT.resolve(), Path(__file__))
    selected_ids = {row["fixture"]["fixture_id"] for row in selected}
    if selected_ids != set(GOOD_PACKS):
        raise SystemExit(f"live_openai_api fixture set drifted: {sorted(selected_ids)}")
    if meta.get("required_fixture_mode") != "live_openai_api" or meta.get("excluded_from_live_api"):
        raise SystemExit(f"OpenAI fixture-mode selection metadata is incorrect: {meta}")

    first_fixture = selected[0]["fixture"]
    first_turn = first_fixture["turns"][0]
    body = build_request_body(package, first_fixture, first_turn, [], args)
    if body.get("model") != OPENAI_MODEL_ID or body.get("store") is not False or body.get("reasoning") != {"effort": "medium"}:
        raise SystemExit("OpenAI request contract drifted.")
    if "tools" in body or body.get("instructions") != package["instructions"]:
        raise SystemExit("OpenAI request must preserve exact Instructions and must not enable tools.")
    if not body.get("input") or body["input"][0].get("role") != "developer" or "GOVERNED_KNOWLEDGE_FILE" not in body["input"][0].get("content", ""):
        raise SystemExit("OpenAI request is missing the governed Knowledge context.")

    sample = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "sample answer"}]}]}
    if extract_text(sample) != "sample answer":
        raise SystemExit("Responses API text extraction failed.")

    rejected_byovd = (
        ("confirmed malicious compromise", "Do not characterize this as confirmed malicious compromise without supporting telemetry."),
        ("logs were cleared", "It cannot establish that logs were cleared without direct evidence."),
    )
    for marker, response in rejected_byovd:
        if score_forbidden_markers(response, [marker])["count"]:
            raise SystemExit(f"Terra BYOVD rejection was scored as affirmative: {marker}")
    affirmative_byovd = (
        ("confirmed malicious compromise", "We characterize this as confirmed malicious compromise."),
        ("logs were cleared", "The evidence establishes that logs were cleared."),
    )
    for marker, response in affirmative_byovd:
        if score_forbidden_markers(response, [marker])["hits"] != [marker]:
            raise SystemExit(f"Terra BYOVD affirmative guard was suppressed: {marker}")

    distributed_collector = """
1. Package/deployment. Upload both files to the endpoint in this order.
upload --file "DCOIR_Collector.ps1"
upload --file "DCOIR_Collector.zip"
They must be placed in the same directory.
2. Endpoint execution. Use execute --command with powershell.exe -File .\DCOIR_Collector.ps1 -Mode Collect -Tier T1.
3. Local validation. Use powershell.exe -File .\DCOIR_Collector.ps1 -Mode Collect -Tier T1 locally.
4. Retrieval. Read NEXT_GET_FILE, then use get-file --path with the exact returned path.
5. Interpret collected output. Review orientation surfaces before raw output.
ANALYST_OVERVIEW_PATH
UPLOAD_SUMMARY_PATH
METADATA_REPORT_PATH
SECURITY_HIGH_SIGNAL_SUMMARY_PATH
6. Cleanup. Use CLEANUP_COMMAND only after required evidence is preserved.
"""
    gaps = collector_procedure_actionability_gaps(distributed_collector)
    if gaps:
        raise SystemExit(f"Distributed Terra collector procedure was not actionable: {gaps}")
    rejected_placement = distributed_collector.replace(
        "They must be placed in the same directory.",
        "Do not place both files in the same directory.",
    )
    if "package_deployment" not in collector_procedure_actionability_gaps(rejected_placement):
        raise SystemExit("Negated same-directory placement incorrectly satisfied package deployment.")
    uploaded_collector = distributed_collector.replace(
        "They must be placed in the same directory.",
        "They must be uploaded in that order to the same directory on the endpoint.",
    )
    if collector_procedure_actionability_gaps(uploaded_collector):
        raise SystemExit("Uploaded same-directory deployment was not recognized as actionable.")
    rejected_upload = distributed_collector.replace(
        "They must be placed in the same directory.",
        "They must not be uploaded to the same directory.",
    )
    if "package_deployment" not in collector_procedure_actionability_gaps(rejected_upload):
        raise SystemExit("Negated uploaded same-directory placement incorrectly satisfied package deployment.")

    live_lane = (
        "Endpoint response actions and local workstation PowerShell are separate execution lanes. "
        "Do not paste response-action syntax into local PowerShell, and do not paste local PowerShell "
        "directly into the Elastic response console."
    )
    if not has_execution_lane_separation(live_lane):
        raise SystemExit("Terra's explicit separate-execution-lanes wording was not recognized.")
    rejected_lane = (
        "It is wrong to say endpoint response actions and local workstation PowerShell are separate execution lanes."
    )
    if has_execution_lane_separation(rejected_lane):
        raise SystemExit("Rejected separate-execution-lanes wording incorrectly passed.")
    for rejected in (
        "Do not say endpoint response actions and local workstation PowerShell are separate execution lanes.",
        "It is not true that endpoint response actions and local workstation PowerShell are separate execution lanes.",
    ):
        if has_execution_lane_separation(rejected):
            raise SystemExit("Negated separate-execution-lanes wording incorrectly passed.")
    contrast_lane = (
        "Do not say endpoint response actions and local workstation PowerShell are separate execution lanes, "
        "but endpoint response actions and local workstation PowerShell are separate execution lanes."
    )
    if not has_execution_lane_separation(contrast_lane):
        raise SystemExit("Contrast reset incorrectly suppressed an affirmative lane-separation statement.")

    entries = {entry["fixture_id"]: entry for entry in load_fixture_index(FIXTURES_ROOT).get("fixtures", [])}
    for fixture_id, pack_name in GOOD_PACKS.items():
        fixture = load_fixture_entry(repo_root, entries[fixture_id])["fixture"]
        pack = json.loads((SUPPORT / pack_name).read_text(encoding="utf-8"))
        pack["mode"] = "live_openai_api"
        pack["model_name"] = OPENAI_MODEL_ID
        messages = validate_response_pack_shape(pack, fixture)
        if any(message.level == "error" for message in messages):
            raise SystemExit(f"Synthetic live OpenAI pack failed schema validation for {fixture_id}: {messages}")
        result = score_response_pack(fixture, pack)
        if not result.get("success"):
            raise SystemExit(f"Known-good response did not pass shared scorer in live_openai_api mode: {fixture_id}")

    fake_responses = {turn["turn_id"]: "not verified workflow state read back one best next move do not guess governed source partial artifact bundle smallest recovery artifact" for turn in first_fixture["turns"]}
    history_lengths = []
    last_history = []
    def fake_call(api_key, project_id, run_args, governed_package, fixture, turn, history):
        history_lengths.append(len(history))
        last_history[:] = list(history)
        return {"ok": True, "attempts": [{"attempt": 1, "status_code": 200}], "response_text": fake_responses[turn["turn_id"]], "response_id": "resp_test"}
    with patch.object(replay_live, "call_openai", side_effect=fake_call):
        generated = make_pack(first_fixture, args, package, "test-key", "")
    if generated.get("mode") != "live_openai_api" or history_lengths != [0, 2, 4, 6]:
        raise SystemExit(f"OpenAI multi-turn local-history contract failed: {history_lengths}")
    sent_prompts = [replay_live.replay_prompt(first_fixture, turn) for turn in first_fixture["turns"][:-1]]
    if [row["content"] for row in last_history if row["role"] == "user"] != sent_prompts:
        raise SystemExit("OpenAI multi-turn history must carry the exact replay prompts (with per-turn evidence) that were sent.")

    secret_value = "sk-test-secret-should-never-persist"
    def fake_secret_echo(api_key, project_id, run_args, governed_package, fixture, turn, history):
        return {"ok": True, "attempts": [{"attempt": 1, "status_code": 200}], "response_text": api_key, "response_id": "resp_secret_test"}
    with patch.object(replay_live, "call_openai", side_effect=fake_secret_echo):
        secret_pack = make_pack(first_fixture, args, package, secret_value, "")
    if secret_value in json.dumps(secret_pack):
        raise SystemExit("Raw API key leaked into the persisted OpenAI replay pack through caller output.")
    if "[redacted-secret-output]" not in json.dumps(secret_pack):
        raise SystemExit("Echoed API key was not replaced by the persisted redaction marker.")

    def fake_failure(api_key, project_id, run_args, governed_package, fixture, turn, history):
        return {
            "ok": False,
            "attempts": [{"attempt": 1, "status_code": 400, "latency_ms": 1.0, "error_body_excerpt": "password=supersecret"}],
            "error": "Authorization: Bearer supersecret",
            "error_body": "Authorization: Bearer supersecret",
        }
    with patch.object(replay_live, "call_openai", side_effect=fake_failure) as failing_call:
        failed_pack = make_pack(first_fixture, args, package, "test-key", "")
    if failing_call.call_count != 1 or len(failed_pack["turns"]) != len(first_fixture["turns"]):
        raise SystemExit("OpenAI replay must stop calling after a failed turn while keeping every turn in the pack.")
    if not all("not_attempted_after_prior_failure" in row["assistant_response"] for row in failed_pack["turns"][1:]):
        raise SystemExit("Turns after a failed call must be marked not attempted.")
    serialized = json.dumps(failed_pack)
    if "supersecret" in serialized or "error_body_excerpt" in serialized or "error_body" in serialized:
        raise SystemExit("Raw provider diagnostics leaked into the persisted OpenAI replay pack.")
    if "runtime_error" not in serialized:
        raise SystemExit("Unsafe provider errors were not reduced to the runtime_error category.")
    class _IncompleteResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def read(self):
            return json.dumps({"id": "resp_cut", "status": "incomplete", "output_text": "partial"}).encode("utf-8")
    with patch.object(replay_live.urllib.request, "urlopen", return_value=_IncompleteResponse()):
        truncated = replay_live.call_openai_body("test-key", "", args, {"model": OPENAI_MODEL_ID})
    if truncated.get("ok") or truncated.get("error") != "incomplete_output":
        raise SystemExit(f"Incomplete Responses API output must not count as a successful call: {truncated}")
    if redact_report_value({"max_output_tokens": 8192}) != {"max_output_tokens": 8192}:
        raise SystemExit("Non-secret max_output_tokens run configuration must not be redacted.")
    redacted = json.dumps(redact_report_value({"error_body_excerpt": "password=supersecret", "status_code": 400}))
    if "supersecret" in redacted or "password=" in redacted:
        raise SystemExit("Workflow report redaction retained raw provider error-body content.")

    print(json.dumps({"success": True, "model": OPENAI_MODEL_ID, "fixture_count": len(selected_ids), "knowledge_file_count": len(package["knowledge_files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
