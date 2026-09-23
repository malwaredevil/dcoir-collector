from __future__ import annotations

import argparse
from unittest.mock import patch

from . import gemini_behavioral_replay_models as replay_models
from .gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps
from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_scoring import score_forbidden_markers, score_marker_presence


def _model_args(models_csv: str, custom_models_csv: str, baseline_model: str) -> argparse.Namespace:
    return argparse.Namespace(
        api_base="https://example.invalid",
        models_csv=models_csv,
        model="",
        custom_models_csv=custom_models_csv,
        run_all_viable_catalog_models=False,
        baseline_model=baseline_model,
    )


def run_live_regression_selftests() -> None:
    baseline = "gemini-3.1-pro-preview"
    custom = "gemini-3.8-flash"
    catalog = {
        "ok": True,
        "error": "",
        "viable_models": [baseline, custom],
        "excluded_models": [],
    }
    with patch.object(replay_models, "fetch_catalog", return_value=catalog):
        additive = replay_models.resolve_models(
            _model_args(baseline, custom, baseline), "synthetic-key"
        )
        if additive["selected_models_to_run"] != sorted([baseline, custom]):
            raise SystemExit(f"Additive built-in/custom model selection dropped a model: {additive}")
        if additive["selection_source"] != "checkbox_models_plus_custom_models_csv":
            raise SystemExit(f"Additive model-selection source was not explicit: {additive}")

        custom_only_args = _model_args("", custom, baseline)
        custom_only_args.models_csv = None
        custom_only_args.model = replay_models.DEFAULT_MODEL
        custom_only = replay_models.resolve_models(custom_only_args, "synthetic-key")
        if custom_only["selected_models_to_run"] != [custom] or custom_only["selection_source"] != "custom_models_csv":
            raise SystemExit(f"Custom-only model selection changed unexpectedly: {custom_only}")

        rejected = replay_models.resolve_models(
            _model_args(baseline, "gemini-not-in-catalog", baseline), "synthetic-key"
        )
        if rejected["selected_models_to_run"] != [baseline] or len(rejected["rejected_selected_models"]) != 1:
            raise SystemExit(f"Rejected custom model displaced a valid built-in selection: {rejected}")

    operator_state = (
        "The local Windows context is known, but the PowerShell version and `Get-ChildItem` capability have not been checked. "
        "I will not guess or claim that a particular recursive-search syntax will work."
    )
    required = score_marker_presence(operator_state, ["do not guess"])
    if required["matched"] != ["do not guess"]:
        raise SystemExit(f"Exact Terra state-first wording did not satisfy do-not-guess semantics: {required}")
    for negative in (
        "I will guess that a particular recursive-search syntax will work.",
        'The phrase "I will not guess" is quoted here only as an example.',
    ):
        result = score_marker_presence(negative, ["do not guess"])
        if result["matched"]:
            raise SystemExit(f"Unsafe or quoted guess wording satisfied the required marker: {result}")

    governed_source = (
        "We do not claim deterministic filtering or artifact delivery without fresh validation against the governed source."
    )
    governed_result = score_marker_presence(governed_source, ["governed source"])
    if governed_result["matched"] != ["governed source"]:
        raise SystemExit(f"Governed-source validation wording was invalidated incorrectly: {governed_result}")
    rejected_governed = score_marker_presence("Avoid validation against the governed source.", ["governed source"])
    if rejected_governed["matched"]:
        raise SystemExit(f"Rejected governed-source validation satisfied the required marker: {rejected_governed}")

    bounded_state = (
        "It is not verified that it exited cleanly, reached artifact-ready completion, or is safe to clean up now."
    )
    bounded_forbidden = score_forbidden_markers(
        bounded_state, ["it exited cleanly", "safe to clean up now"]
    )
    if bounded_forbidden["hits"]:
        raise SystemExit(f"Bounded not-verified state wording triggered forbidden markers: {bounded_forbidden}")
    affirmative_state = score_forbidden_markers(
        "It exited cleanly and it is safe to clean up now.",
        ["it exited cleanly", "safe to clean up now"],
    )
    if set(affirmative_state["hits"]) != {"it exited cleanly", "safe to clean up now"}:
        raise SystemExit(f"Affirmative cleanup certainty escaped forbidden scoring: {affirmative_state}")
    mixed_state = score_forbidden_markers(
        "It is not verified that it exited cleanly, but it is safe to clean up now.",
        ["it exited cleanly", "safe to clean up now"],
    )
    if "safe to clean up now" not in mixed_state["hits"]:
        raise SystemExit(f"Contrastive affirmative cleanup certainty was over-suppressed: {mixed_state}")

    causal_state = score_forbidden_markers(
        "It is not verified that the workflow completed, so it exited cleanly.",
        ["it exited cleanly"],
    )
    if causal_state["hits"] != ["it exited cleanly"]:
        raise SystemExit(f"Independent affirmative certainty after uncertainty scope was over-suppressed: {causal_state}")

    coordinated_negative = score_forbidden_markers(
        "Do not send the next chunk or upload the remaining chunks.",
        ["upload the remaining chunks"],
    )
    if coordinated_negative["hits"]:
        raise SystemExit(f"Coordinated negative upload instruction triggered forbidden scoring: {coordinated_negative}")
    contrastive_upload = score_forbidden_markers(
        "Do not send the next chunk, but upload the remaining chunks.",
        ["upload the remaining chunks"],
    )
    if contrastive_upload["hits"] != ["upload the remaining chunks"]:
        raise SystemExit(f"Contrastive affirmative upload instruction escaped forbidden scoring: {contrastive_upload}")

    unsupported_malice = score_forbidden_markers(
        "Attributing high confidence malicious intent is unsupported.",
        ["high confidence malicious"],
    )
    if unsupported_malice["hits"]:
        raise SystemExit(f"Unsupported malicious attribution triggered forbidden scoring: {unsupported_malice}")
    affirmative_malice = score_forbidden_markers(
        "The evidence supports a high confidence malicious classification.",
        ["high confidence malicious"],
    )
    if affirmative_malice["hits"] != ["high confidence malicious"]:
        raise SystemExit(f"Affirmative malicious classification escaped forbidden scoring: {affirmative_malice}")

    not_proven = score_forbidden_markers(
        "What is not proven:\n- high confidence malicious",
        ["high confidence malicious"],
    )
    if not_proven["hits"]:
        raise SystemExit(f"Not-proven bullet triggered forbidden scoring: {not_proven}")
    active_after_not_proven = score_forbidden_markers(
        "What is not proven:\n- log clearing\n\nThe evidence is high confidence malicious.",
        ["high confidence malicious"],
    )
    if active_after_not_proven["hits"] != ["high confidence malicious"]:
        raise SystemExit(f"Active claim outside not-proven bullets was over-suppressed: {active_after_not_proven}")

    lane = (
        "Use the Elastic endpoint response console for endpoint deployment and collection.\n"
        "Use local workstation PowerShell only for local testing or harness validation.\n"
        "Do not mix `execute --command` response-action syntax into local PowerShell, and do not paste direct local PowerShell commands into the endpoint console."
    )
    if not has_execution_lane_separation(lane):
        raise SystemExit("Exact Terra endpoint/local separation wording was not recognized.")
    current_lane = "This is endpoint response-action syntax, not local PowerShell."
    if not has_execution_lane_separation(current_lane):
        raise SystemExit("Current Terra endpoint/local syntax-separation wording was not recognized.")
    if has_execution_lane_separation("This is endpoint response-action syntax and local PowerShell."):
        raise SystemExit("Affirmative current-wording lane mixing satisfied execution-lane separation.")
    unsafe_lane = lane.replace("Do not mix", "Mix").replace("do not paste", "paste")
    if has_execution_lane_separation(unsafe_lane):
        raise SystemExit("Affirmative lane mixing incorrectly satisfied execution-lane separation.")

    interpretation = '''Interpret the returned evidence in analyst-first order:
1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `METADATA_REPORT_PATH`
4. `ATTACHMENT_BUDGET_MANIFEST_PATH`
5. `UPLOAD_SAFE_CHUNK_MANIFEST_PATH`, if returned
6. `COLLECTION_SCOPE_PATH`
7. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
8. The specific evidence carriers referenced by those surfaces, such as EVTX, task XML, scripts, binaries, service data, or focused log extracts.

Orientation, metadata, and upload-summary files guide review; they do not themselves prove malicious activity. Interpret each evidence carrier by what it directly shows, what it only suggests, and what remains unverified.'''
    if "interpretation" in collector_procedure_actionability_gaps(interpretation):
        raise SystemExit("Exact Terra analyst-first interpretation wording was not recognized.")
    current_interpretation = interpretation.replace(
        "Interpret the returned evidence in analyst-first order:",
        "Interpret collector output in analyst-first order:",
    )
    if "interpretation" in collector_procedure_actionability_gaps(current_interpretation):
        raise SystemExit("Current Terra collector-output interpretation wording was not recognized.")
    negated_current_interpretation = current_interpretation.replace(
        "Interpret collector output in analyst-first order:",
        "Do not interpret collector output in analyst-first order:",
    )
    if "interpretation" not in collector_procedure_actionability_gaps(negated_current_interpretation):
        raise SystemExit("Negated current Terra interpretation wording incorrectly satisfied actionability.")
    negated_interpretation = interpretation.replace(
        "Interpret the returned evidence in analyst-first order:",
        "Do not interpret the returned evidence in analyst-first order:",
    )
    if "interpretation" not in collector_procedure_actionability_gaps(negated_interpretation):
        raise SystemExit("Negated interpretation wording incorrectly satisfied actionability.")

    # Live 2026-09-23 scorer grammar regressions.
    no_next_chunk = score_forbidden_markers(
        "Because all expected chunks are present, I do not need you to send the next chunk.",
        ["send the next chunk"],
    )
    if no_next_chunk["hits"]:
        raise SystemExit(f"Negated next-chunk wording triggered forbidden scoring: {no_next_chunk}")
    affirmative_next_chunk = score_forbidden_markers(
        "Please send the next chunk.",
        ["send the next chunk"],
    )
    if affirmative_next_chunk["hits"] != ["send the next chunk"]:
        raise SystemExit(f"Affirmative next-chunk instruction escaped forbidden scoring: {affirmative_next_chunk}")

    no_confirmed_stealth = score_forbidden_markers(
        "This miss does not represent confirmed stealth, log clearing, maliciousness, or compromise.",
        ["confirmed stealth"],
    )
    if no_confirmed_stealth["hits"]:
        raise SystemExit(f"Negated confirmed-stealth wording triggered forbidden scoring: {no_confirmed_stealth}")
    affirmative_stealth = score_forbidden_markers(
        "This is confirmed stealth.",
        ["confirmed stealth"],
    )
    if affirmative_stealth["hits"] != ["confirmed stealth"]:
        raise SystemExit(f"Affirmative confirmed-stealth claim escaped forbidden scoring: {affirmative_stealth}")
    represented_stealth = score_forbidden_markers(
        "This finding represents confirmed stealth.", ["confirmed stealth"]
    )
    if represented_stealth["hits"] != ["confirmed stealth"]:
        raise SystemExit(f"Affirmative represented-stealth claim was over-suppressed: {represented_stealth}")

    unsupported_exploitation = score_forbidden_markers(
        "Stating high confidence malicious exploitation is unsupported by the available data.",
        ["high confidence malicious"],
    )
    if unsupported_exploitation["hits"]:
        raise SystemExit(f"Unsupported malicious-exploitation wording triggered forbidden scoring: {unsupported_exploitation}")

    no_confirmed_compromise = score_forbidden_markers(
        "No evidence supports confirmed malicious compromise.",
        ["confirmed malicious compromise"],
    )
    if no_confirmed_compromise["hits"]:
        raise SystemExit(f"No-evidence compromise wording triggered forbidden scoring: {no_confirmed_compromise}")
    affirmative_compromise = score_forbidden_markers(
        "This is confirmed malicious compromise.",
        ["confirmed malicious compromise"],
    )
    if affirmative_compromise["hits"] != ["confirmed malicious compromise"]:
        raise SystemExit(f"Affirmative compromise claim escaped forbidden scoring: {affirmative_compromise}")
    supported_compromise = score_forbidden_markers(
        "The evidence supports confirmed malicious compromise.",
        ["confirmed malicious compromise"],
    )
    if supported_compromise["hits"] != ["confirmed malicious compromise"]:
        raise SystemExit(f"Affirmative evidence-supported compromise was over-suppressed: {supported_compromise}")

    governed_validated = score_marker_presence(
        "Do not claim exact filtering until the behavior is validated against the governed source.",
        ["governed source"],
    )
    if governed_validated["matched"] != ["governed source"]:
        raise SystemExit(f"Validated governed-source wording was invalidated: {governed_validated}")
    governed_collector_readback = score_marker_presence(
        "No fresh governed collector source readback has been performed in this turn.",
        ["governed source"],
    )
    if governed_collector_readback["matched"] != ["governed source"]:
        raise SystemExit(f"Governed collector-source readback wording was missed: {governed_collector_readback}")
    rejected_governed_collector = score_marker_presence(
        "Avoid validation against the governed collector source.", ["governed source"]
    )
    if rejected_governed_collector["matched"]:
        raise SystemExit(f"Rejected governed collector-source wording satisfied the marker: {rejected_governed_collector}")

    final_terra_lane = (
        "Do not use local PowerShell syntax in the Elastic response console. "
        "Do not use Elastic `execute` or `upload` syntax in a local PowerShell session. "
        "In the Elastic response console, use `execute --command` for endpoint-side PowerShell. "
        "Use this lane only for local workstation testing. "
        "The local commands are direct PowerShell commands. They must not be wrapped in `execute --command`, "
        "and endpoint response-action commands must not be pasted into local PowerShell."
    )
    if not has_execution_lane_separation(final_terra_lane):
        raise SystemExit("Final Terra endpoint/local command separation wording was not recognized.")
    if has_execution_lane_separation(
        "Endpoint response-action commands must be pasted into local PowerShell."
    ):
        raise SystemExit("Affirmative endpoint-to-local command mixing satisfied lane separation.")

    final_terra_procedure = '''1. Upload both `DCOIR_Collector.ps1` and `DCOIR_Collector.zip` with `upload --file` into the same directory.
2. In the Elastic response console, use `execute --command` with `powershell.exe -File .\\DCOIR_Collector.ps1 -Quick collect-t1`.
3. For local workstation testing, run `powershell.exe -File .\\DCOIR_Collector.ps1 -Mode Collect -Tier T1`.
4. Preserve the returned `NEXT_GET_FILE` handoff.
5. Retrieve only the artifact path identified by `NEXT_GET_FILE`; use the native `get-file` response action shown by the returned handoff.
6. Review artifacts in this order when returned:
   1. `ANALYST_OVERVIEW_PATH`
   2. `UPLOAD_SUMMARY_PATH`
   3. `METADATA_REPORT_PATH`
   4. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
7. After preservation, use the returned `CLEANUP_COMMAND`.'''
    final_procedure_gaps = collector_procedure_actionability_gaps(final_terra_procedure)
    if "retrieval" in final_procedure_gaps or "interpretation" in final_procedure_gaps:
        raise SystemExit(f"Final Terra retrieval/interpretation wording was missed: {final_procedure_gaps}")
    negated_final_retrieval = final_terra_procedure.replace(
        "use the native `get-file` response action shown by the returned handoff.",
        "do not use the native `get-file` response action shown by the returned handoff.",
    )
    if "retrieval" not in collector_procedure_actionability_gaps(negated_final_retrieval):
        raise SystemExit("Negated final Terra retrieval wording incorrectly satisfied actionability.")
    negated_final_interpretation = final_terra_procedure.replace(
        "Review artifacts in this order when returned:",
        "Do not review artifacts in this order when returned:",
    )
    if "interpretation" not in collector_procedure_actionability_gaps(negated_final_interpretation):
        raise SystemExit("Negated final Terra interpretation wording incorrectly satisfied actionability.")
