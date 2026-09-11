"""DCOIR Review v57 final-adjudication low-confidence terminal disposition.

Live run 34566845633 completed the deep detector, quality retry, independent
challenger, and final v35 semantic adjudicator, then failed only because every
remaining adjudicated hypothesis was below the configured publication confidence
floor.

v57 preserves the historical fail-closed contract for earlier-stage weak output,
malformed findings, unanchored findings, summary-only concerns, adjudication
overflow, required deterministic risk sentinels, verifier failures,
exact-head/publication failures, and v44/v52 candidate-escalation adjudication.
It recognizes only a completed final v35 semantic-adjudication result whose
remaining findings are complete, changed-line-anchored, actionable-shaped,
finite-confidence candidates and are all strictly below the active publication
floor, whose original summary is a non-empty string that does not itself indicate
a problem, and whose adjudication result was not overflow-trimmed. That terminal
state is recorded as an explicit clean disposition instead of raising
ReviewQualityError.

The overlay also injects the active publication floor only into the final v35
semantic-adjudicator prompt while preserving v54's semantic-adjudicator telemetry
classification so other semantic escalation contracts and run accounting remain
unchanged.
"""

from __future__ import annotations

import copy
import inspect
import math
from typing import Any

import dcoir_review_required_runtime_patch_v54 as v54


VERSION = "v57"
APPLIED_MARKER = "_dcoir_review_v57_applied"
SPLIT_STORAGE = "_dcoir_review_v57_original_split_findings_with_review_body_fallback"
REVIEW_STORAGE = "_dcoir_review_v57_original_openrouter_review"
DISPOSITION_MARKER = "_dcoir_v57_terminal_low_confidence_disposition"
PROMPT_INJECTION_ATTR = "_dcoir_v57_publication_floor_injected"
PROMPT_MARKER = "DCOIR downstream publication confidence floor:"
FINAL_ADJUDICATION_PROMPT_MARKER = "Candidate hypotheses from the earlier detector/challenger stages:"
PROMPT_TRUNCATION_MARKER = "\n\n[semantic adjudication PR evidence truncated by reviewer budget]"
PROMPT_ARTIFACT_PATH = "prompts/06-semantic-adjudication-prompt.txt"
CLEAN_SUMMARY = "No high confidence findings were found after semantic adjudication."
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_REQUIRED_FINDING_FIELDS = (
    "title",
    "severity",
    "confidence",
    "path",
    "line",
    "body",
    "suggested_replacement",
    "validation",
)
_STRING_FINDING_FIELDS = ("title", "severity", "path", "body", "suggested_replacement", "validation")


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        parsed = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return None
    return parsed


def _publication_floor(config: Any) -> float | None:
    return _confidence(getattr(config, "minimum_confidence", None))


def _complete_subthreshold_candidate(
    module: Any,
    item: Any,
    floor: float,
    line_index: dict[tuple[str, int], int],
) -> tuple[dict[str, Any], float] | None:
    """Return a complete, changed-line-anchored candidate below the floor."""

    if not isinstance(item, dict):
        return None
    if set(item.keys()) != set(_REQUIRED_FINDING_FIELDS):
        return None
    if any(not isinstance(item.get(field), str) for field in _STRING_FINDING_FIELDS):
        return None
    for field in ("title", "severity", "path", "body", "validation"):
        if not str(item.get(field) or "").strip():
            return None
    # Detector/adjudicator responses are required to leave repair text empty;
    # a non-empty replacement is a malformed semantic result, not a weak finding.
    if str(item.get("suggested_replacement", "") or ""):
        return None
    if item.get("severity") not in _VALID_SEVERITIES:
        return None

    raw_line = item.get("line")
    if isinstance(raw_line, bool) or not isinstance(raw_line, int) or raw_line <= 0:
        return None
    path = str(item.get("path", "") or "").strip()
    if (path, raw_line) not in line_index:
        return None

    confidence = _confidence(item.get("confidence"))
    if confidence is None or confidence >= floor:
        return None

    try:
        if module.hardened.non_actionable_finding_reason(item):
            return None
    except Exception:
        # If the active quality classifier cannot be consulted, keep the
        # historical fail-closed path rather than silently withdrawing output.
        return None

    return dict(item), confidence


def _required_sentinels_present(module: Any, risk_sentinels: list[Any]) -> bool:
    try:
        required = module.hardened.required_risk_sentinels(risk_sentinels)
    except Exception:
        # Sentinel-classification uncertainty must never enable the clean path.
        return True
    return bool(required)


def _summary_allows_clean(module: Any, result: dict[str, Any], config: Any) -> bool:
    """Honor the existing summary-only problem gate before clearing findings."""

    raw_summary = result.get("summary")
    if not isinstance(raw_summary, str) or not raw_summary.strip():
        return False
    if not bool(getattr(config, "fail_on_summary_only_problem", True)):
        return True
    try:
        return not bool(module.hardened.summary_suggests_problem(raw_summary.strip()))
    except Exception:
        # If the active summary classifier is unavailable or fails, preserve the
        # historical fail-closed behavior rather than replacing the summary.
        return False


def _completed_final_adjudication_matches_result(result: dict[str, Any], raw_findings: list[Any]) -> bool:
    """Require internally recorded final-v35-adjudication evidence for this result."""

    if result.get("_semantic_adjudication_attempted") is not True:
        return False
    model = result.get("_semantic_adjudication_model")
    if not isinstance(model, str) or not model.strip():
        return False
    input_count = result.get("_semantic_adjudication_input_candidates")
    if isinstance(input_count, bool) or not isinstance(input_count, int) or input_count <= 0:
        return False

    # v35 stamps this marker only when it had to trim an over-limit adjudicator
    # response. That pre-cap response is not safe to reinterpret as clean because
    # discarded entries can include malformed/non-object output.
    if "_semantic_adjudication_overflow_trimmed" in result:
        return False

    output_count = result.get("_semantic_adjudication_output_findings")
    if isinstance(output_count, bool) or not isinstance(output_count, int):
        return False
    if output_count != len(raw_findings):
        return False

    # v44/v55 explicitly stamp their escalation scope. The live #546 failure
    # came from v35, which does not set this marker. Keep those later contracts
    # byte-for-byte on their existing v52/v55 disposition path.
    if "_semantic_adjudication_context_scope" in result:
        return False
    return True


def _terminal_disposition(
    module: Any,
    result: Any,
    config: Any,
    line_index: dict[tuple[str, int], int],
    risk_sentinels: list[Any] | None,
) -> dict[str, Any] | None:
    """Classify only the final-v35 all-sub-threshold terminal shape."""

    if not isinstance(result, dict) or not isinstance(line_index, dict):
        return None

    raw_findings = result.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return None
    if not _completed_final_adjudication_matches_result(result, raw_findings):
        return None
    if not _summary_allows_clean(module, result, config):
        return None

    sentinels = list(risk_sentinels or [])
    if _required_sentinels_present(module, sentinels):
        return None

    floor = _publication_floor(config)
    if floor is None:
        return None

    candidates: list[dict[str, Any]] = []
    confidences: list[float] = []
    for raw in raw_findings:
        qualified = _complete_subthreshold_candidate(module, raw, floor, line_index)
        if qualified is None:
            return None
        item, confidence = qualified
        candidates.append(item)
        confidences.append(confidence)

    return {
        "version": VERSION,
        "candidate_count": len(candidates),
        "minimum_confidence": floor,
        "lowest_confidence": min(confidences),
        "highest_confidence": max(confidences),
        "adjudication_model": str(result.get("_semantic_adjudication_model", "") or ""),
        "adjudication_scope": "final-v35",
        "candidates": [
            {
                "path": str(item.get("path", "") or ""),
                "line": int(item.get("line", 0) or 0),
                "severity": str(item.get("severity", "") or ""),
                "confidence": confidence,
                "title": str(item.get("title", "") or "")[:120],
            }
            for item, confidence in zip(candidates, confidences)
        ],
    }


def _record_terminal_disposition(module: Any, result: dict[str, Any], disposition: dict[str, Any], config: Any) -> None:
    result[DISPOSITION_MARKER] = disposition
    result["findings"] = []
    result["summary"] = CLEAN_SUMMARY

    try:
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/v57-terminal-low-confidence-disposition.json",
            disposition,
        )
    except Exception:
        # Debug evidence is best-effort and must not turn a valid semantic
        # disposition back into a workflow failure.
        pass

    try:
        emit = getattr(module.base, "emit_status", None)
        if callable(emit):
            emit(
                "terminal-low-confidence-disposition",
                (
                    f"version={VERSION}; candidates={disposition['candidate_count']}; "
                    f"publication_floor={float(disposition['minimum_confidence']):.2f}; "
                    f"confidence_range={float(disposition['lowest_confidence']):.2f}-"
                    f"{float(disposition['highest_confidence']):.2f}; result=clean"
                ),
            )
    except Exception:
        pass


def _inject_publication_floor(prompt: Any, config: Any) -> Any:
    if not isinstance(prompt, str):
        return prompt
    if bool(getattr(config, PROMPT_INJECTION_ATTR, False)):
        return prompt
    if not _is_final_v35_semantic_adjudication_call(prompt):
        return prompt

    floor = _publication_floor(config)
    if floor is None:
        return prompt

    instruction = (
        f"- {PROMPT_MARKER} {floor:.2f}. Return a finding only when its confidence is at least "
        f"{floor:.2f}. If no defect meets this floor, return an empty findings list and a clean summary."
    )
    needle = "Publication-quality rules:"
    if needle in prompt:
        injected = prompt.replace(needle, f"{needle}\n{instruction}", 1)
    else:
        injected = f"{instruction}\n\n{prompt}"
    return _apply_prompt_budget(injected, config)


def _is_final_v35_semantic_adjudication_call(prompt: Any) -> bool:
    frame = inspect.currentframe()
    current = frame.f_back if frame is not None else None
    try:
        while current is not None:
            filename = str(current.f_code.co_filename or "").replace("\\", "/").rsplit("/", 1)[-1]
            function = current.f_code.co_name
            locals_map = current.f_locals
            if (
                filename == "dcoir_review_required_runtime_patch_v35.py"
                and function == "openrouter_review_with_hybrid_first_pass"
                and locals_map.get("prompt") is prompt
            ):
                return True
            current = current.f_back
    finally:
        del frame
    return False


def _apply_prompt_budget(prompt: str, config: Any) -> str:
    try:
        max_prompt_chars = int(getattr(config, "max_prompt_chars", 120000))
    except (OverflowError, TypeError, ValueError):
        max_prompt_chars = 120000
    if max_prompt_chars <= 0:
        return ""
    if len(prompt) <= max_prompt_chars:
        return prompt
    if max_prompt_chars <= len(PROMPT_TRUNCATION_MARKER):
        return PROMPT_TRUNCATION_MARKER[:max_prompt_chars]
    return (
        prompt[: max(0, max_prompt_chars - len(PROMPT_TRUNCATION_MARKER))]
        + PROMPT_TRUNCATION_MARKER
    )


def _patch_openrouter_review(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, REVIEW_STORAGE, None)
    if original is None:
        original = getattr(hardened, "openrouter_review", None)
        if callable(original):
            setattr(hardened, REVIEW_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v57 could not locate hardened openrouter_review")

    def openrouter_review(prompt, schema, config, reporter=None):
        injected = _inject_publication_floor(prompt, config)
        if injected is prompt:
            return original(prompt, schema, config, reporter)

        # v54 normally recognizes the final v35 semantic-adjudicator call from
        # prompt object identity. Injection necessarily creates a new str, so
        # preserve the stage explicitly on a shallow config projection before
        # forwarding through the already-installed v54 telemetry wrapper.
        try:
            staged = copy.copy(config)
            setattr(staged, v54.STAGE_LABEL_ATTR, "semantic-adjudicator")
            setattr(staged, PROMPT_INJECTION_ATTR, True)
        except Exception:
            # Prompt-floor injection is advisory. If stage preservation cannot be
            # established safely, retain original behavior and telemetry rather
            # than mutating the call in a way v54 would misclassify.
            return original(prompt, schema, config, reporter)
        try:
            module.hardened.write_debug_text_artifact_safely(
                config,
                PROMPT_ARTIFACT_PATH,
                injected,
            )
        except Exception as exc:
            # Debug artifact emission is best-effort only; never block adjudication.
            try:
                module.hardened.write_debug_text_artifact_safely(
                    config,
                    "dcoir_review_v57_prompt_floor_injection_error.txt",
                    repr(exc),
                )
            except Exception:
                # If even diagnostic emission fails, continue silently to preserve
                # existing runtime behavior.
                pass
        return original(injected, schema, staged, reporter)

    hardened.openrouter_review = openrouter_review


def _patch_terminal_split(module: Any) -> None:
    original = getattr(module, SPLIT_STORAGE, None)
    if original is None:
        original = getattr(module, "split_findings_with_review_body_fallback", None)
        if callable(original):
            setattr(module, SPLIT_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v57 could not locate split_findings_with_review_body_fallback")

    def split_findings_with_review_body_fallback(
        result,
        config,
        line_index,
        diff="",
        risk_sentinels=None,
    ):
        disposition = _terminal_disposition(module, result, config, line_index, risk_sentinels)
        if disposition is not None:
            _record_terminal_disposition(module, result, disposition, config)
            return [], []
        return original(result, config, line_index, diff, risk_sentinels)

    module.split_findings_with_review_body_fallback = split_findings_with_review_body_fallback


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_openrouter_review(module)
    _patch_terminal_split(module)
    setattr(module, APPLIED_MARKER, True)
