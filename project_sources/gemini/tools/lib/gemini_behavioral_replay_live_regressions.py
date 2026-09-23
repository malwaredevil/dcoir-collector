from __future__ import annotations

import argparse
from unittest.mock import patch

from . import gemini_behavioral_replay_models as replay_models
from .gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps
from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_scoring import score_marker_presence


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

    lane = (
        "Use the Elastic endpoint response console for endpoint deployment and collection.\n"
        "Use local workstation PowerShell only for local testing or harness validation.\n"
        "Do not mix `execute --command` response-action syntax into local PowerShell, and do not paste direct local PowerShell commands into the endpoint console."
    )
    if not has_execution_lane_separation(lane):
        raise SystemExit("Exact Terra endpoint/local separation wording was not recognized.")
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
    negated_interpretation = interpretation.replace(
        "Interpret the returned evidence in analyst-first order:",
        "Do not interpret the returned evidence in analyst-first order:",
    )
    if "interpretation" not in collector_procedure_actionability_gaps(negated_interpretation):
        raise SystemExit("Negated interpretation wording incorrectly satisfied actionability.")
