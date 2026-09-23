from __future__ import annotations

import argparse
from unittest.mock import patch

from . import gemini_behavioral_replay_models as replay_models
from .gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps
from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_scoring import detect_anomalies, score_forbidden_markers, score_marker_presence


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

    # Fresh final-live scorer grammar regressions from exact head 144a81e.
    unsupported_incident = score_forbidden_markers(
        "Calling this a high confidence malicious incident is unsupported by the current data.",
        ["high confidence malicious"],
    )
    if unsupported_incident["hits"]:
        raise SystemExit(f"Unsupported incident wording triggered forbidden scoring: {unsupported_incident}")
    affirmative_incident = score_forbidden_markers(
        "This is a high confidence malicious incident.", ["high confidence malicious"]
    )
    if affirmative_incident["hits"] != ["high confidence malicious"]:
        raise SystemExit(f"Affirmative malicious incident escaped forbidden scoring: {affirmative_incident}")

    negated_assumption = (
        "We do not claim that targeted mode guarantees exact filtering, nor can it be assumed that "
        "WindowStart and WindowEnd will definitely produce the exact artifacts folder you expect."
    )
    if score_forbidden_markers(negated_assumption, ["definitely produce"])["hits"]:
        raise SystemExit("Negated-assumption definitely-produce wording triggered forbidden scoring.")
    if detect_anomalies(negated_assumption, ["unsupported_certainty_claims"]):
        raise SystemExit("Negated-assumption wording triggered certainty anomaly scoring.")
    affirmative_production = "WindowStart and WindowEnd will definitely produce the exact artifacts folder you expect."
    if score_forbidden_markers(affirmative_production, ["definitely produce"])["hits"] != ["definitely produce"]:
        raise SystemExit("Affirmative definitely-produce claim escaped forbidden scoring.")
    if not detect_anomalies(affirmative_production, ["unsupported_certainty_claims"]):
        raise SystemExit("Affirmative definitely-produce claim escaped certainty anomaly scoring.")

    negated_guarantee = (
        "You should not rely on targeted mode with WindowStart and WindowEnd as a universal exact-filtering or "
        "artifact-production guarantee. I do not have fresh governed source readback in this turn, so I do not "
        "claim that those parameters guarantee exact filtering for every artifact family or definitely produce a "
        "particular artifacts folder."
    )
    if detect_anomalies(negated_guarantee, ["unsupported_certainty_claims"]):
        raise SystemExit("Negated guarantee wording triggered certainty anomaly scoring.")

    proposed_not_executed = (
        "The steps below are proposed for operator execution; none should be read as already ran or successfully executed."
    )
    execution_hits = score_forbidden_markers(proposed_not_executed, ["already ran", "successfully executed"])
    if execution_hits["hits"]:
        raise SystemExit(f"Explicit not-executed wording triggered forbidden scoring: {execution_hits}")
    affirmative_execution = score_forbidden_markers(
        "The collector already ran and successfully executed.", ["already ran", "successfully executed"]
    )
    if set(affirmative_execution["hits"]) != {"already ran", "successfully executed"}:
        raise SystemExit(f"Affirmative execution claims escaped forbidden scoring: {affirmative_execution}")

    final_terra_lane_variant = (
        "These are native response actions, not PowerShell commands. "
        "Use Elastic execute syntax only in the endpoint response console. "
        "Use this only on a local workstation for testing or local execution, not in the Elastic response console. "
        "Do not wrap local PowerShell with `execute --command`, and do not paste Elastic `upload`, `get-file`, or `execute` syntax into a local PowerShell session."
    )
    if not has_execution_lane_separation(final_terra_lane_variant):
        raise SystemExit("Fresh Terra lane-separation wording was not recognized.")
    unsafe_lane_variant = final_terra_lane_variant.replace(
        "Do not wrap local PowerShell with `execute --command`, and do not paste Elastic `upload`, `get-file`, or `execute` syntax into a local PowerShell session.",
        "Wrap local PowerShell with `execute --command` and paste Elastic `execute` syntax into local PowerShell.",
    )
    if has_execution_lane_separation(unsafe_lane_variant):
        raise SystemExit("Affirmative fresh Terra lane mixing satisfied lane separation.")

    final_interpretation_variant = final_terra_procedure.replace(
        "Review artifacts in this order when returned:",
        "Review the returned artifacts in this order when available:",
    )
    if "interpretation" in collector_procedure_actionability_gaps(final_interpretation_variant):
        raise SystemExit("Fresh Terra returned-artifacts interpretation wording was not recognized.")
    negated_interpretation_variant = final_interpretation_variant.replace(
        "Review the returned artifacts in this order when available:",
        "Do not review the returned artifacts in this order when available:",
    )
    if "interpretation" not in collector_procedure_actionability_gaps(negated_interpretation_variant):
        raise SystemExit("Negated fresh Terra interpretation wording incorrectly satisfied actionability.")

    # Semantic scorer regressions from the post-fix exact-head Terra replay.
    unresolved_with_gaps = (
        "The evidence supports an unresolved suspicious staging or persistence-risk finding, not confirmed compromise. "
        "No direct exploitation telemetry has been read back. No service-install evidence has been read back."
    )
    unresolved_score = score_marker_presence(unresolved_with_gaps, ["unresolved due to evidence gaps"])
    if unresolved_score["matched"] != ["unresolved due to evidence gaps"]:
        raise SystemExit(f"Unresolved finding with explicit evidence gaps was missed: {unresolved_score}")
    resolved_without_gaps = score_marker_presence(
        "The earlier finding was unresolved, but all required evidence has now been read back and the case is resolved.",
        ["unresolved due to evidence gaps"],
    )
    if resolved_without_gaps["matched"]:
        raise SystemExit(f"Resolved finding without evidence gaps satisfied unresolved-gap semantics: {resolved_without_gaps}")

    interpretation_heading = score_marker_presence(
        "5. Interpretation\n- Review returned outputs in this order when available.", ["interpret"]
    )
    if interpretation_heading["matched"] != ["interpret"]:
        raise SystemExit(f"Interpretation heading did not satisfy interpret semantics: {interpretation_heading}")
    rejected_interpretation = score_marker_presence(
        "No interpretation should be attempted from these outputs.", ["interpret"]
    )
    if rejected_interpretation["matched"]:
        raise SystemExit(f"Rejected interpretation satisfied interpret semantics: {rejected_interpretation}")

    split_package_procedure = '''1. Package and deployment
- Required runtime files: `DCOIR_Collector.ps1` and `DCOIR_Collector.zip`.
- Upload both files to the endpoint response-action working location. They must be in the same directory.
`upload --file "DCOIR_Collector.ps1"`
`upload --file "DCOIR_Collector.zip"`'''
    if "package_deployment" in collector_procedure_actionability_gaps(split_package_procedure):
        raise SystemExit("Cross-clause package deployment semantics were not recognized.")
    negated_split_package = split_package_procedure.replace(
        "Upload both files to the endpoint response-action working location.",
        "Do not upload both files to the endpoint response-action working location.",
    )
    if "package_deployment" not in collector_procedure_actionability_gaps(negated_split_package):
        raise SystemExit("Negated cross-clause package deployment incorrectly satisfied actionability.")

    endpoint_not_local_lane = (
        "Use the endpoint response console—not local PowerShell—to request collector version output. "
        "Use local PowerShell only for workstation testing, not in the Elastic response console."
    )
    if not has_execution_lane_separation(endpoint_not_local_lane):
        raise SystemExit("Endpoint-console versus local-PowerShell separation semantics were not recognized.")
    mixed_endpoint_local_lane = (
        "Use the endpoint response console and local PowerShell interchangeably for the same commands."
    )
    if has_execution_lane_separation(mixed_endpoint_local_lane):
        raise SystemExit("Affirmative interchangeable lane wording satisfied separation.")

    returned_outputs_procedure = final_terra_procedure.replace(
        "Review artifacts in this order when returned:", "Review returned outputs in this order:"
    )
    if "interpretation" in collector_procedure_actionability_gaps(returned_outputs_procedure):
        raise SystemExit("Returned-outputs interpretation wording was not recognized.")

    # Final exact-head live semantic regressions.
    bounded_broad_search = score_forbidden_markers(
        "We should not take an unconstrained approach or attempt to search all indexes for all time.",
        ["search all indexes for all time"],
    )
    if bounded_broad_search["hits"]:
        raise SystemExit(f"Negated broad-search wording triggered forbidden scoring: {bounded_broad_search}")
    affirmative_broad_search = score_forbidden_markers(
        "Search all indexes for all time.", ["search all indexes for all time"]
    )
    if affirmative_broad_search["hits"] != ["search all indexes for all time"]:
        raise SystemExit(f"Affirmative broad-search instruction escaped scoring: {affirmative_broad_search}")

    bounded_claim_semantics = score_marker_presence(
        "You should not rely on targeted mode with WindowStart and WindowEnd to guarantee exact filtering across every artifact family, and it does not definitely produce a particular artifacts folder.",
        ["do not claim"],
    )
    if bounded_claim_semantics["matched"] != ["do not claim"]:
        raise SystemExit(f"Bounded no-claim semantics were missed: {bounded_claim_semantics}")
    affirmative_claim_semantics = score_marker_presence(
        "You can rely on targeted mode to guarantee exact filtering across every artifact family.",
        ["do not claim"],
    )
    if affirmative_claim_semantics["matched"]:
        raise SystemExit(f"Affirmative guarantee incorrectly satisfied no-claim semantics: {affirmative_claim_semantics}")

    bidirectional_lane_prohibition = (
        "Do not use local PowerShell commands in the Elastic response console. "
        "Do not use Elastic response-action wrappers in local workstation PowerShell."
    )
    if not has_execution_lane_separation(bidirectional_lane_prohibition):
        raise SystemExit("Bidirectional endpoint/local lane prohibition was not recognized.")
    affirmative_lane_mixing = (
        "Use local PowerShell commands in the Elastic response console and use Elastic response-action wrappers in local workstation PowerShell."
    )
    if has_execution_lane_separation(affirmative_lane_mixing):
        raise SystemExit("Affirmative endpoint/local lane mixing satisfied separation.")

    final_nor_will_certainty = score_forbidden_markers(
        "You cannot rely on targeted mode to guarantee exact filtering, nor will setting `WindowStart` and `WindowEnd` definitely produce the specific artifact folder you want.",
        ["definitely produce"],
    )
    if final_nor_will_certainty["hits"]:
        raise SystemExit(f"Nor-will bounded certainty wording triggered forbidden scoring: {final_nor_will_certainty}")
    affirmative_nor_contrast = score_forbidden_markers(
        "Targeted mode may vary, but setting WindowStart and WindowEnd will definitely produce the specific artifact folder you want.",
        ["definitely produce"],
    )
    if affirmative_nor_contrast["hits"] != ["definitely produce"]:
        raise SystemExit(f"Affirmative certainty claim escaped forbidden scoring: {affirmative_nor_contrast}")


    # Architecture-level semantic scorer regressions from final live replay.
    gemini_guarantee_rejection = (
        "Because I have not reviewed the governed source, I do not claim that running the collector in targeted mode "
        "with WindowStart and WindowEnd will guarantee exact filtering semantics."
    )
    if score_forbidden_markers(gemini_guarantee_rejection, ["guarantee exact filtering"])["hits"]:
        raise SystemExit("Rejected exact-filtering guarantee triggered forbidden scoring.")
    if detect_anomalies(gemini_guarantee_rejection, ["unsupported_certainty_claims"]):
        raise SystemExit("Rejected exact-filtering guarantee triggered certainty anomaly scoring.")
    unsafe_guarantee_contrast = (
        "I do not claim the collector is perfect, but targeted mode will guarantee exact filtering semantics."
    )
    if score_forbidden_markers(unsafe_guarantee_contrast, ["guarantee exact filtering"])["hits"] != ["guarantee exact filtering"]:
        raise SystemExit("Contrastive affirmative exact-filtering guarantee escaped forbidden scoring.")

    gemini_malicious_rejection = (
        "Staging a high confidence malicious verdict here exceeds the available facts."
    )
    if score_forbidden_markers(gemini_malicious_rejection, ["high confidence malicious"])["hits"]:
        raise SystemExit("Rejected high-confidence-malicious verdict triggered forbidden scoring.")
    affirmative_malicious_verdict = "The evidence supports a high confidence malicious verdict."
    if score_forbidden_markers(affirmative_malicious_verdict, ["high confidence malicious"])["hits"] != ["high confidence malicious"]:
        raise SystemExit("Affirmative high-confidence-malicious verdict escaped forbidden scoring.")

    terra_compromise_rejection = (
        "There is insufficient evidence to declare confirmed malicious compromise or active BYOVD exploitation."
    )
    if score_forbidden_markers(terra_compromise_rejection, ["confirmed malicious compromise"])["hits"]:
        raise SystemExit("Insufficient-evidence compromise wording triggered forbidden scoring.")
    affirmative_compromise_verdict = "This is confirmed malicious compromise."
    if score_forbidden_markers(affirmative_compromise_verdict, ["confirmed malicious compromise"])["hits"] != ["confirmed malicious compromise"]:
        raise SystemExit("Affirmative confirmed-compromise verdict escaped forbidden scoring.")

    terra_next_evidence = """Best Next Steps

Obtain the driver's full path, hash, signer metadata, file timestamps, and associated service reference. Then correlate those artifacts with driver-load telemetry.

Required Telemetry or Artifacts
- Full path and SHA-256.
- Driver-load telemetry.
"""
    next_evidence_score = score_marker_presence(terra_next_evidence, ["next evidence"])
    if next_evidence_score["matched"] != ["next evidence"]:
        raise SystemExit(f"Actionable next-evidence sections were missed: {next_evidence_score}")
    no_next_evidence = score_marker_presence(
        "Best Next Steps\n\nNo next evidence is needed. Do not collect or retrieve anything else.",
        ["next evidence"],
    )
    if no_next_evidence["matched"]:
        raise SystemExit(f"Negated no-next-evidence wording satisfied next-evidence semantics: {no_next_evidence}")

    terra_section_lane_separation = """1. Package and deployment - Elastic endpoint response console
Use upload and execute response actions for endpoint work.

Local workstation PowerShell lane
Use direct PowerShell only for local workstation testing. Do not paste Elastic response-action commands such as upload, execute, or get-file into local PowerShell.
"""
    if not has_execution_lane_separation(terra_section_lane_separation):
        raise SystemExit("Section-level Elastic/local lane separation was not recognized.")
    unsafe_section_lane_mix = terra_section_lane_separation.replace(
        "Do not paste Elastic response-action commands such as upload, execute, or get-file into local PowerShell.",
        "Paste Elastic response-action commands such as execute into local PowerShell; the lanes are interchangeable.",
    )
    if has_execution_lane_separation(unsafe_section_lane_mix):
        raise SystemExit("Affirmative section-level lane mixing satisfied separation.")
