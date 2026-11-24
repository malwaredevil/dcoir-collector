"""Stable final semantic-adjudication publication and disposition policy."""

from __future__ import annotations

import copy
import inspect
from typing import Any

from dcoir_review import semantic_adjudication_quality_retry as quality_retry
from dcoir_review import review_telemetry
from dcoir_review import terminal_low_confidence_disposition as terminal


APPLIED_MARKER = "_dcoir_review_final_adjudication_policy_applied"
PROMPT_INJECTION_ATTR = "_dcoir_v57_publication_floor_injected"
PROMPT_MARKER = "DCOIR downstream publication confidence floor:"
FINAL_ADJUDICATION_PROMPT_MARKER = "Candidate hypotheses from the earlier detector/challenger stages:"
PROMPT_TRUNCATION_MARKER = "\n\n[semantic adjudication PR evidence truncated by reviewer budget]"
PROMPT_ARTIFACT_PATH = "prompts/06-semantic-adjudication-prompt.txt"


def _inject_publication_floor(prompt: Any, config: Any) -> Any:
    if not isinstance(prompt, str):
        return prompt
    if bool(getattr(config, PROMPT_INJECTION_ATTR, False)):
        return prompt
    if not (
        bool(getattr(config, quality_retry.FINAL_ADJUDICATION_RETRY_ATTR, False))
        or _is_final_semantic_adjudication_call(prompt)
    ):
        return prompt

    floor = terminal.publication_floor(config)
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


def _is_final_semantic_adjudication_call(prompt: Any) -> bool:
    frame = inspect.currentframe()
    current = frame.f_back if frame is not None else None
    try:
        while current is not None:
            filename = str(current.f_code.co_filename or "").replace("\\", "/").rsplit("/", 1)[-1]
            function = current.f_code.co_name
            locals_map = current.f_locals
            if (
                filename == "semantic_adjudication.py"
                and function in (
                    "openrouter_review_with_hybrid_first_pass",
                    "semantic_adjudication_stage",
                )
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



def project_review_call(module: Any, prompt: Any, config: Any) -> tuple[Any, Any]:
    try:
        injected = _inject_publication_floor(prompt, config)
    except Exception:
        return prompt, config
    if injected is prompt:
        return prompt, config
    try:
        staged = copy.copy(config)
        setattr(staged, review_telemetry.STAGE_LABEL_ATTR, "semantic-adjudicator")
        setattr(staged, PROMPT_INJECTION_ATTR, True)
    except Exception:
        return prompt, config
    try:
        artifact_path = (
            quality_retry.projected_prompt_artifact_path(config)
            if getattr(config, quality_retry.FINAL_ADJUDICATION_RETRY_ATTR, False)
            else PROMPT_ARTIFACT_PATH
        )
        module.hardened.write_debug_text_artifact_safely(
            config, artifact_path, injected
        )
    except Exception:
        # Debug-artifact persistence is observational and must not alter review flow.
        return injected, staged
    return injected, staged


def _install_terminal_split(module: Any) -> None:
    original = getattr(module, "split_findings_with_review_body_fallback", None)
    if not callable(original):
        raise RuntimeError(
            "DCOIR final adjudication policy could not locate "
            "split_findings_with_review_body_fallback"
        )

    def split_findings_with_review_body_fallback(
        result, config, line_index, diff="", risk_sentinels=None
    ):
        disposition = terminal.terminal_disposition(
            module, result, config, line_index, risk_sentinels
        )
        if disposition is not None:
            terminal.record_terminal_disposition(module, result, disposition, config)
            return [], []
        try:
            return original(result, config, line_index, diff, risk_sentinels)
        except module.hardened.ReviewQualityError:
            # A sub-floor-only model result must not suppress the required
            # deterministic sentinel findings that the caller adds next.
            fallback = terminal.sentinel_fallback_disposition(
                module, result, config, line_index, risk_sentinels
            )
            if fallback is None:
                raise
            terminal.record_terminal_disposition(
                module, result, fallback, config,
                terminal.SENTINEL_FALLBACK_MARKER, terminal.SENTINEL_FALLBACK_SUMMARY,
            )
            return [], []

    module.split_findings_with_review_body_fallback = (
        split_findings_with_review_body_fallback
    )


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _install_terminal_split(module)
    setattr(module, APPLIED_MARKER, True)
