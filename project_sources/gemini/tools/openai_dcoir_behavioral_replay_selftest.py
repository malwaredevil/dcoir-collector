#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import lib.openai_dcoir_replay_live as replay_live
import lib.gemini_behavioral_replay_selection as replay_selection

build_request_body = replay_live.build_request_body
extract_text = replay_live.extract_text
make_pack = replay_live.make_pack

from lib.gemini_behavioral_replay_prompt import behavioral_replay_prompt
from lib.gemini_behavioral_replay_runner import load_fixture_entry, load_fixture_index, repo_root_from_script
from lib.gemini_behavioral_replay_utils import safe_error
from lib.gemini_behavioral_replay_schema import ValidationMessage, validate_fixture_shape, validate_response_pack_shape
from lib.gemini_behavioral_replay_scoring import detect_anomalies, score_forbidden_markers, score_response_pack
from lib.gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps
from lib.gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
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
    selected, meta = replay_selection.resolve_fixtures(args, FIXTURES_ROOT.resolve(), Path(__file__))
    selected_ids = {row["fixture"]["fixture_id"] for row in selected}
    if selected_ids != set(GOOD_PACKS):
        raise SystemExit(f"live_openai_api fixture set drifted: {sorted(selected_ids)}")
    if meta.get("required_fixture_mode") != "live_openai_api" or meta.get("excluded_from_live_api"):
        raise SystemExit(f"OpenAI fixture-mode selection metadata is incorrect: {meta}")

    none_args = argparse.Namespace(**{**vars(args), "run_all_active_fixtures": False, "fixture_ids_csv": "", "custom_fixtures_csv": ""})
    none_selected, none_meta = replay_selection.resolve_fixtures(none_args, FIXTURES_ROOT.resolve(), Path(__file__))
    if none_selected or none_meta.get("selected_fixtures_to_run"):
        raise SystemExit(f"Blank OpenAI fixture selection must fail closed, not select billable fixtures: {none_meta}")

    first_fixture = selected[0]["fixture"]
    invalid_args = argparse.Namespace(**{**vars(args), "run_all_active_fixtures": False, "custom_fixtures_csv": first_fixture["fixture_id"]})
    invalid_row = {
        "fixture": first_fixture,
        "validation_messages": [ValidationMessage("error", "synthetic fixture validation failure")],
    }
    with patch.object(replay_selection, "load_fixture_entry", return_value=invalid_row):
        invalid_selected, invalid_meta = replay_selection.resolve_fixtures(
            invalid_args, FIXTURES_ROOT.resolve(), Path(__file__)
        )
    if invalid_selected or invalid_meta.get("selected_fixtures_to_run"):
        raise SystemExit(f"Schema-invalid fixture must not reach live replay execution: {invalid_meta}")
    if not any("fixture validation failed" in row.get("reason", "") for row in invalid_meta.get("rejected_selected_fixtures", [])):
        raise SystemExit(f"Schema-invalid fixture rejection reason was not preserved: {invalid_meta}")

    malformed_scalar_fixture = json.loads(json.dumps(first_fixture))
    malformed_scalar_fixture["turns"][0]["content"] = None
    malformed_scalar_row = {
        "fixture": malformed_scalar_fixture,
        "validation_messages": validate_fixture_shape(malformed_scalar_fixture),
    }
    with patch.object(replay_selection, "load_fixture_entry", return_value=malformed_scalar_row):
        scalar_selected, scalar_meta = replay_selection.resolve_fixtures(
            invalid_args, FIXTURES_ROOT.resolve(), Path(__file__)
        )
    if scalar_selected or scalar_meta.get("selected_fixtures_to_run"):
        raise SystemExit(f"Malformed scalar fixture must be rejected before live replay execution: {scalar_meta}")
    if not any("field content must be a non-empty string" in row.get("reason", "") for row in scalar_meta.get("rejected_selected_fixtures", [])):
        raise SystemExit(f"Malformed scalar fixture rejection reason was not preserved: {scalar_meta}")

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

    if extract_text({"output": None}) or extract_text(["wrong-shape"]):
        raise SystemExit("Malformed/null Responses API output must extract as empty text.")
    for malformed_output in (1, True, {}, "bad"):
        if extract_text({"status": "completed", "output": malformed_output}):
            raise SystemExit(f"Malformed Responses API output container must extract as empty text: {malformed_output!r}")
    for malformed_content in (1, True, {}, "bad"):
        if extract_text({"status": "completed", "output": [{"type": "message", "content": malformed_content}]}):
            raise SystemExit(f"Malformed Responses API content container must extract as empty text: {malformed_content!r}")

    rejected_byovd = (
        ("confirmed malicious compromise", "Do not characterize this as confirmed malicious compromise without supporting telemetry."),
        ("logs were cleared", "It cannot establish that logs were cleared without direct evidence."),
    )
    for marker, response in rejected_byovd:
        if score_forbidden_markers(response, [marker])["count"]:
            raise SystemExit(f"Terra BYOVD rejection was scored as affirmative: {marker}")
    mixed_certainty = detect_anomalies(
        "We checked the supplied evidence and confirmed the vulnerable driver is present. "
        "Separately, the host is confirmed malicious compromise and certainly malicious.",
        ["unsupported_certainty_claims"],
    )
    if not {row["detail"] for row in mixed_certainty}.issuperset({"certainly", "confirmed"}):
        raise SystemExit(f"Later unsupported certainty was masked by an earlier supported use: {mixed_certainty}")

    affirmative_byovd = (
        ("confirmed malicious compromise", "We characterize this as confirmed malicious compromise."),
        ("logs were cleared", "The evidence establishes that logs were cleared."),
    )
    for marker, response in affirmative_byovd:
        if score_forbidden_markers(response, [marker])["hits"] != [marker]:
            raise SystemExit(f"Terra BYOVD affirmative guard was suppressed: {marker}")

    distributed_collector = r"""
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
    for unsafe in (
        "Don't be afraid to paste the response-action syntax into local PowerShell.",
        "Do not stop until you paste the response-action syntax into local PowerShell.",
        "Do not stop before you paste the response-action syntax into local PowerShell.",
        "Do not be reluctant to paste the response-action syntax into local PowerShell.",
        "Do not avoid pasting the response-action syntax into local PowerShell.",
        "Use the endpoint response console whether or not local PowerShell is also open.",
    ):
        if has_execution_lane_separation(unsafe):
            raise SystemExit(f"Unsafe/ambiguous lane wording incorrectly passed separation: {unsafe}")
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
    for status_payload, expected_error in (
        ({"id": "resp_missing_status", "output_text": "safe"}, "invalid_response_shape"),
        ({"id": "resp_null_status", "status": None, "output_text": "safe"}, "invalid_response_shape"),
        ({"id": "resp_bool_status", "status": True, "output_text": "safe"}, "invalid_response_shape"),
        ({"id": "resp_num_status", "status": 1, "output_text": "safe"}, "invalid_response_shape"),
        ({"id": "resp_unknown_status", "status": "mystery", "output_text": "safe"}, "incomplete_output"),
    ):
        class _StatusResponse(_IncompleteResponse):
            def read(self, payload=status_payload):
                return json.dumps(payload).encode("utf-8")
        with patch.object(replay_live.urllib.request, "urlopen", return_value=_StatusResponse()):
            status_result = replay_live.call_openai_body("test-key", "", args, {"model": OPENAI_MODEL_ID})
        if status_result.get("ok") or status_result.get("error") != expected_error:
            raise SystemExit(f"Malformed/missing Responses status must fail before scoring: {status_payload!r}: {status_result}")

    class _WrongShapeResponse(_IncompleteResponse):
        def read(self):
            return b'[]'
    with patch.object(replay_live.urllib.request, "urlopen", return_value=_WrongShapeResponse()):
        wrong_shape = replay_live.call_openai_body("test-key", "", args, {"model": OPENAI_MODEL_ID})
    if wrong_shape.get("ok") or wrong_shape.get("error") != "invalid_response_shape":
        raise SystemExit(f"Wrong-shaped Responses API JSON must fail without traceback: {wrong_shape}")
    class _NullOutputResponse(_IncompleteResponse):
        def read(self):
            return b'{"id":"resp_null","status":"completed","output":null}'
    with patch.object(replay_live.urllib.request, "urlopen", return_value=_NullOutputResponse()):
        null_output = replay_live.call_openai_body("test-key", "", args, {"model": OPENAI_MODEL_ID})
    if null_output.get("ok") or null_output.get("error") != "empty_output":
        raise SystemExit(f"Null Responses API output must fail cleanly as empty_output: {null_output}")
    for malformed_payload in (
        {"id": "resp_num", "status": "completed", "output": 1},
        {"id": "resp_bool", "status": "completed", "output": True},
        {"id": "resp_obj", "status": "completed", "output": {}},
        {"id": "resp_nested_num", "status": "completed", "output": [{"type": "message", "content": 1}]},
        {"id": "resp_nested_bool", "status": "completed", "output": [{"type": "message", "content": True}]},
        {"id": "resp_nested_obj", "status": "completed", "output": [{"type": "message", "content": {}}]},
        {"id": "resp_output_item", "status": "completed", "output": [1]},
        {"id": "resp_content_item", "status": "completed", "output": [{"type": "message", "content": [1]}]},
        {"id": "resp_text_type", "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": 7}]}]},
        {"id": "resp_direct_type", "status": "completed", "output_text": 7, "output": []},
        {"id": "resp_direct_nested_num", "status": "completed", "output_text": "safe", "output": 1},
        {"id": "resp_direct_nested_content_bool", "status": "completed", "output_text": "safe", "output": [{"type": "message", "content": True}]},
        {"id": "resp_direct_nested_text_num", "status": "completed", "output_text": "safe", "output": [{"type": "message", "content": [{"type": "output_text", "text": 123}]}]},
        {"id": "resp_direct_conflict", "status": "completed", "output_text": "safe", "output": [{"type": "message", "content": [{"type": "output_text", "text": "different"}]}]},
    ):
        class _MalformedShapeResponse(_IncompleteResponse):
            def read(self, payload=malformed_payload):
                return json.dumps(payload).encode("utf-8")
        with patch.object(replay_live.urllib.request, "urlopen", return_value=_MalformedShapeResponse()):
            malformed_shape = replay_live.call_openai_body("test-key", "", args, {"model": OPENAI_MODEL_ID})
        if malformed_shape.get("ok") or malformed_shape.get("error") != "invalid_response_shape":
            raise SystemExit(f"Malformed nested Responses API shape must fail cleanly: {malformed_payload!r}: {malformed_shape}")
    consistent_dual = replay_live._extract_text_with_shape({
        "status": "completed",
        "output_text": "safe",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "safe"}]}],
    })
    if consistent_dual != ("safe", True):
        raise SystemExit(f"Consistent direct/nested Responses output must remain valid: {consistent_dual}")

    retry_args = argparse.Namespace(**{**vars(args), "max_retries": 3, "retry_base_seconds": 0.0})
    for raised, expected_error, expected_calls in (
        (TimeoutError("read timed out"), "read_timeout", 1),
        (ConnectionResetError("reset after send"), "runtime_error", 1),
        (replay_live.urllib.error.URLError("connection refused"), "connection_error", 3),
    ):
        with patch.object(replay_live.urllib.request, "urlopen", side_effect=raised) as posted:
            outcome = replay_live.call_openai_body("test-key", "", retry_args, {"model": OPENAI_MODEL_ID})
        if outcome.get("ok") or safe_error(outcome.get("error")) != expected_error or posted.call_count != expected_calls:
            raise SystemExit(f"Retry policy wrong for {type(raised).__name__}: {outcome} after {posted.call_count} POSTs")

    class _MalformedResponse(_IncompleteResponse):
        def read(self):
            return b"<html>not json</html>"
    with patch.object(replay_live.urllib.request, "urlopen", return_value=_MalformedResponse()) as posted:
        malformed = replay_live.call_openai_body("test-key", "", retry_args, {"model": OPENAI_MODEL_ID})
    if malformed.get("error") != "invalid_json" or posted.call_count != 1:
        raise SystemExit(f"A malformed 200 body must fail once without re-POSTing: {malformed}")

    if replay_live.replay_prompt(first_fixture, first_fixture["turns"][0]) != behavioral_replay_prompt(
        first_fixture, first_fixture["turns"][0], replay_label="DCOIR behavioral replay"
    ):
        raise SystemExit("OpenAI replay prompt must come from the shared behavioral replay prompt builder.")
    for scalar_key, scalar_value in (
        ("speaker", None), ("speaker", []), ("speaker", "   "), ("speaker", "assistant"),
        ("content", None), ("content", []), ("content", "   "),
        ("scoring_notes", None), ("scoring_notes", []), ("scoring_notes", "   "),
    ):
        malformed_scalar = json.loads(json.dumps(first_fixture))
        malformed_scalar["turns"][0][scalar_key] = scalar_value
        scalar_messages = validate_fixture_shape(malformed_scalar)
        expected_scalar_error = (
            "speaker must be 'user'" if scalar_key == "speaker" and scalar_value == "assistant"
            else f"field {scalar_key} must be a non-empty string"
        )
        if not any(message.level == "error" and expected_scalar_error in message.message for message in scalar_messages):
            raise SystemExit(f"Malformed scalar turn field must fail schema validation: {scalar_key}={scalar_value!r}: {scalar_messages}")
        try:
            behavioral_replay_prompt(malformed_scalar, malformed_scalar["turns"][0], replay_label="DCOIR behavioral replay")
        except ValueError:
            pass
        else:
            raise SystemExit(f"Prompt builder must fail closed on malformed scalar field {scalar_key}={scalar_value!r}")

    for anomaly_value in (None, 7, "   ", [""], ["unknown_check"]):
        malformed_anomaly = json.loads(json.dumps(first_fixture))
        malformed_anomaly["turns"][0]["anomaly_checks"] = anomaly_value
        anomaly_messages = validate_fixture_shape(malformed_anomaly)
        if not any(message.level == "error" and "anomaly_checks" in message.message for message in anomaly_messages):
            raise SystemExit(f"Malformed/unknown anomaly_checks must fail schema validation: {anomaly_value!r}: {anomaly_messages}")
        anomaly_row = {"fixture": malformed_anomaly, "validation_messages": anomaly_messages}
        with patch.object(replay_selection, "load_fixture_entry", return_value=anomaly_row):
            anomaly_selected, anomaly_meta = replay_selection.resolve_fixtures(
                invalid_args, FIXTURES_ROOT.resolve(), Path(__file__)
            )
        if anomaly_selected or anomaly_meta.get("selected_fixtures_to_run"):
            raise SystemExit(f"Invalid anomaly_checks fixture must be rejected before live replay execution: {anomaly_meta}")
    for fixture_key, bad_value in (
        ("fixture_id", None),
        ("title", []),
        ("source_issue_numbers", "bad"),
        ("scenario_tags", {}),
        ("artifact_inputs", "bad"),
        ("expected_behaviors", 7),
        ("pass_thresholds", "bad"),
        ("report_expectations", []),
    ):
        malformed_required = json.loads(json.dumps(first_fixture))
        malformed_required[fixture_key] = bad_value
        required_messages = validate_fixture_shape(malformed_required)
        if not any(message.level == "error" and fixture_key in message.message for message in required_messages):
            raise SystemExit(f"Malformed required fixture field must fail schema validation: {fixture_key}={bad_value!r}: {required_messages}")

    malformed_fixture_anomaly = json.loads(json.dumps(first_fixture))
    malformed_fixture_anomaly["anomaly_checks"] = ["unknown_check"]
    fixture_anomaly_messages = validate_fixture_shape(malformed_fixture_anomaly)
    if not any(message.level == "error" and "fixture anomaly_checks" in message.message for message in fixture_anomaly_messages):
        raise SystemExit(f"Unknown fixture-level anomaly check must fail schema validation: {fixture_anomaly_messages}")

    malformed_fixture = json.loads(json.dumps(first_fixture))
    malformed_fixture["turns"][0]["allowed_assumptions"] = None
    malformed_messages = validate_fixture_shape(malformed_fixture)
    if not any(message.level == "error" and "allowed_assumptions must be a list" in message.message for message in malformed_messages):
        raise SystemExit(f"Null list-valued fixture field must fail schema validation: {malformed_messages}")
    try:
        behavioral_replay_prompt(malformed_fixture, malformed_fixture["turns"][0], replay_label="DCOIR behavioral replay")
    except ValueError as exc:
        if "allowed_assumptions must be a list" not in str(exc):
            raise SystemExit(f"Prompt builder rejected malformed data with the wrong reason: {exc}")
    else:
        raise SystemExit("Prompt builder must fail closed if malformed list-valued fixture data bypasses validation.")
    malformed_structures = [
        ([None], "turn entry must be an object"),
        (["bad"], "turn entry must be an object"),
    ]
    for turns_value, expected_error in malformed_structures:
        malformed = json.loads(json.dumps(first_fixture))
        malformed["turns"] = turns_value
        messages = validate_fixture_shape(malformed)
        if not any(message.level == "error" and expected_error in message.message for message in messages):
            raise SystemExit(f"Malformed turn structure must fail validation: {messages}")
    malformed_profile = json.loads(json.dumps(first_fixture))
    malformed_profile["model_target_profile"] = None
    profile_messages = validate_fixture_shape(malformed_profile)
    if not any(message.level == "error" and "model_target_profile must be an object" in message.message for message in profile_messages):
        raise SystemExit(f"Null model_target_profile must fail validation: {profile_messages}")
    if not any(message.level == "error" for message in validate_fixture_shape([])):
        raise SystemExit("Non-object fixture root must fail validation without raising.")
    try:
        behavioral_replay_prompt({}, None, replay_label="DCOIR behavioral replay")
    except ValueError as exc:
        if "turn_id must be a non-empty string" not in str(exc):
            raise SystemExit(f"Empty fixture/turn must fail closed with the expected reason: {exc}")
    else:
        raise SystemExit("Empty fixture/turn must fail closed before prompt construction.")
    malformed_turn_id = json.loads(json.dumps(first_fixture))
    malformed_turn_id["turns"][0]["turn_id"] = []
    turn_id_messages = validate_fixture_shape(malformed_turn_id)
    if not any(message.level == "error" and "turn_id must be a non-empty string" in message.message for message in turn_id_messages):
        raise SystemExit(f"Unhashable turn_id must fail validation without raising: {turn_id_messages}")
    malformed_markers = json.loads(json.dumps(first_fixture))
    malformed_markers["turns"][0]["required_markers"] = [None, 7]
    marker_messages = validate_fixture_shape(malformed_markers)
    if not any(message.level == "error" and "required_markers must contain only non-empty strings" in message.message for message in marker_messages):
        raise SystemExit(f"Non-string marker elements must fail validation: {marker_messages}")
    try:
        behavioral_replay_prompt(malformed_markers, malformed_markers["turns"][0], replay_label="DCOIR behavioral replay")
    except ValueError as exc:
        if "required_markers must contain only non-empty strings" not in str(exc):
            raise SystemExit(f"Prompt builder rejected malformed markers with the wrong reason: {exc}")
    else:
        raise SystemExit("Prompt builder must fail closed on malformed marker elements.")
    whitespace_fixture = json.loads(json.dumps(first_fixture))
    whitespace_fixture["turns"][0]["forbidden_markers"] = ["   "]
    whitespace_messages = validate_fixture_shape(whitespace_fixture)
    if not any(message.level == "error" and "forbidden_markers must contain only non-empty strings" in message.message for message in whitespace_messages):
        raise SystemExit(f"Whitespace-only marker elements must fail validation: {whitespace_messages}")
    try:
        behavioral_replay_prompt(whitespace_fixture, whitespace_fixture["turns"][0], replay_label="DCOIR behavioral replay")
    except ValueError as exc:
        if "forbidden_markers must contain only non-empty strings" not in str(exc):
            raise SystemExit(f"Prompt builder rejected whitespace markers with the wrong reason: {exc}")
    else:
        raise SystemExit("Prompt builder must fail closed on whitespace-only marker elements.")
    runner_source = (repo_root / "project_sources/gemini/tools/run_openai_dcoir_behavioral_replay.py").read_text(encoding="utf-8")
    for required_evidence_label in ("MARKER_ASSISTED_UNCHECKED_EVIDENCE,", '"prompt_profile": PROMPT_PROFILE'):
        if required_evidence_label not in runner_source:
            raise SystemExit(f"OpenAI DCOIR replay must record the marker-assisted evidence gap: {required_evidence_label}")
    if redact_report_value({"max_output_tokens": 8192}) != {"max_output_tokens": 8192}:
        raise SystemExit("Non-secret max_output_tokens run configuration must not be redacted.")
    redacted = json.dumps(redact_report_value({"error_body_excerpt": "password=supersecret", "status_code": 400}))
    if "supersecret" in redacted or "password=" in redacted:
        raise SystemExit("Workflow report redaction retained raw provider error-body content.")

    print(json.dumps({"success": True, "model": OPENAI_MODEL_ID, "fixture_count": len(selected_ids), "knowledge_file_count": len(package["knowledge_files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
