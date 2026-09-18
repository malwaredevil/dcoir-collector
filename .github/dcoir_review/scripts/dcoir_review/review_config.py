"""Canonical post-base configuration for DCOIR Review.

The base Pareto loader parses configuration once. This module owns the
responsibility-specific settings that historical runtime overlays used to add by
wrapping ``load_pareto_context_config``. Keeping those settings here makes
configuration composition explicit without preserving the runtime wrapper chain.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIRMATION_MODELS = ("openai/gpt-5.6-sol-pro",)
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_VERIFIER_REPAIR_LIMIT = 8
DEFAULT_ADJUDICATION_MODELS = (
    "anthropic/claude-opus-5",
    "openai/gpt-5.6-sol-pro",
)
DEFAULT_ADJUDICATION_MAX_FINDINGS = 8
DEFAULT_CANDIDATE_DIGEST_CHARS = 24000
DEFAULT_CANDIDATE_ESCALATION_CONFIDENCE_MARGIN = 0.10
DEFAULT_CANDIDATE_ESCALATION_MAX_PATHS = 4
DEFAULT_CANDIDATE_ESCALATION_FILE_CHARS = 12000
DEFAULT_CANDIDATE_ESCALATION_TOTAL_CONTEXT_CHARS = 48000
DEFAULT_REPAIR_CRITIC_BATCH_MAX_FINDINGS = 8

ADAPTIVE_SEMANTIC_DEFAULTS = {
    "adaptive_semantic_min_prompt_chars": 48000,
    "adaptive_semantic_small_delta_prompt_chars": 60000,
    "adaptive_semantic_small_delta_max_files": 4,
    "adaptive_semantic_small_delta_max_diff_chars": 20000,
    "adaptive_semantic_small_delta_max_context_chars": 30000,
}


def _as_string_list(value: Any, fallback: tuple[str, ...]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback)


def _optional_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, parsed)


def _optional_positive_int(value: Any, key: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Config key {key!r} must be a positive integer or empty, got {value!r}"
        ) from exc
    if parsed <= 0:
        raise ValueError(
            f"Config key {key!r} must be a positive integer or empty, got {value!r}"
        )
    return parsed


def _unit_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if 0.0 <= parsed <= 1.0 else fallback


def _apply_adversarial_confirmation(config: Any, data: dict[str, Any], hardened: Any) -> None:
    config.adversarial_confirmation_review = hardened.bool_value(
        data, "adversarial_confirmation_review", True
    )
    config.adversarial_confirmation_model_stack = _as_string_list(
        data.get("adversarial_confirmation_model_stack"),
        DEFAULT_CONFIRMATION_MODELS,
    )
    config.review_reasoning_effort = str(
        data.get("review_reasoning_effort", DEFAULT_REASONING_EFFORT)
        or DEFAULT_REASONING_EFFORT
    ).strip()

    try:
        configured = int(
            getattr(config, "fix_synthesis_max_findings", DEFAULT_VERIFIER_REPAIR_LIMIT)
        )
    except (TypeError, ValueError):
        configured = DEFAULT_VERIFIER_REPAIR_LIMIT
    try:
        inline_limit = int(getattr(config, "max_inline_comments", configured))
    except (TypeError, ValueError):
        inline_limit = configured
    verifier_repair_limit = max(1, min(configured, inline_limit))

    from dcoir_review import finding_verifier, repair_pipeline

    finding_verifier.VERIFIER_MAX_MODEL_FINDINGS = verifier_repair_limit
    repair_pipeline.MAX_REPAIR_CANDIDATES = verifier_repair_limit
    config.dcoir_v32_verifier_repair_limit = verifier_repair_limit


def _apply_semantic_adjudication(config: Any, data: dict[str, Any], hardened: Any) -> None:
    config.semantic_adjudication_review = hardened.bool_value(
        data, "semantic_adjudication_review", True
    )
    config.semantic_adjudication_model_stack = _as_string_list(
        data.get("semantic_adjudication_model_stack"),
        DEFAULT_ADJUDICATION_MODELS,
    )
    configured_max = _positive_int(
        data.get("semantic_adjudication_max_findings", DEFAULT_ADJUDICATION_MAX_FINDINGS),
        DEFAULT_ADJUDICATION_MAX_FINDINGS,
    )
    inline_max = _positive_int(
        getattr(config, "max_inline_comments", configured_max),
        configured_max,
    )
    config.semantic_adjudication_max_findings = min(configured_max, inline_max)
    config.semantic_adjudication_candidate_digest_chars = _positive_int(
        data.get(
            "semantic_adjudication_candidate_digest_chars",
            DEFAULT_CANDIDATE_DIGEST_CHARS,
        ),
        DEFAULT_CANDIDATE_DIGEST_CHARS,
    )


def _apply_candidate_escalation(config: Any, data: dict[str, Any], hardened: Any) -> None:
    config.candidate_scoped_escalation_review = hardened.bool_value(
        data, "candidate_scoped_escalation_review", True
    )
    config.candidate_escalation_confidence_margin = _unit_float(
        data.get(
            "candidate_escalation_confidence_margin",
            DEFAULT_CANDIDATE_ESCALATION_CONFIDENCE_MARGIN,
        ),
        DEFAULT_CANDIDATE_ESCALATION_CONFIDENCE_MARGIN,
    )
    config.candidate_escalation_max_paths = _positive_int(
        data.get(
            "candidate_escalation_max_paths",
            DEFAULT_CANDIDATE_ESCALATION_MAX_PATHS,
        ),
        DEFAULT_CANDIDATE_ESCALATION_MAX_PATHS,
    )
    config.candidate_escalation_file_chars = _positive_int(
        data.get(
            "candidate_escalation_file_chars",
            DEFAULT_CANDIDATE_ESCALATION_FILE_CHARS,
        ),
        DEFAULT_CANDIDATE_ESCALATION_FILE_CHARS,
    )
    config.candidate_escalation_total_context_chars = _positive_int(
        data.get(
            "candidate_escalation_total_context_chars",
            DEFAULT_CANDIDATE_ESCALATION_TOTAL_CONTEXT_CHARS,
        ),
        DEFAULT_CANDIDATE_ESCALATION_TOTAL_CONTEXT_CHARS,
    )


def _apply_publication_and_context(config: Any, data: dict[str, Any], hardened: Any) -> None:
    config.verifier_authoritative_publication_review = hardened.bool_value(
        data, "verifier_authoritative_publication_review", True
    )
    config.canonical_semantic_context_review = hardened.bool_value(
        data, "canonical_semantic_context_review", True
    )
    config.adaptive_semantic_budgets_review = hardened.bool_value(
        data, "adaptive_semantic_budgets_review", True
    )
    for key, fallback in ADAPTIVE_SEMANTIC_DEFAULTS.items():
        setattr(config, key, _positive_int(data.get(key, fallback), fallback))
    config.verified_finding_gate_state_review = hardened.bool_value(
        data, "verified_finding_gate_state_review", True
    )
    config.semantic_candidate_identity_review = hardened.bool_value(
        data, "semantic_candidate_identity_review", True
    )


def _apply_per_file_routing(config: Any, data: dict[str, Any]) -> None:
    config.per_file_review_model_stack = _optional_string_list(
        data.get("per_file_review_model_stack")
    )
    effort = str(data.get("per_file_review_reasoning_effort", "") or "").strip()
    config.per_file_review_reasoning_effort = effort or None
    config.per_file_review_max_tokens = _optional_positive_int(
        data.get("per_file_review_max_tokens"),
        "per_file_review_max_tokens",
    )
    config.per_file_review_provider_sort = str(
        data.get("per_file_review_provider_sort", "") or ""
    ).strip()


def _initialize_run_telemetry_fail_soft(config: Any) -> None:
    try:
        from dcoir_review import review_telemetry as telemetry

        telemetry.ensure_sink(config)
    except Exception:
        try:
            telemetry.note_telemetry_error(config)
        except Exception:
            # Telemetry is observational only; config loading must remain available
            # even when recording the telemetry failure also fails.
            return


def _apply_repair_critic_batching(config: Any, data: dict[str, Any], hardened: Any) -> None:
    config.repair_critic_batching_enabled = hardened.bool_value(
        data, "repair_critic_batching_enabled", True
    )
    raw_limit = data.get(
        "repair_critic_batch_max_findings",
        DEFAULT_REPAIR_CRITIC_BATCH_MAX_FINDINGS,
    )
    try:
        config.repair_critic_batch_max_findings = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Config key 'repair_critic_batch_max_findings' must be an integer"
        ) from exc


def apply_review_config(config: Any, data: dict[str, Any], hardened: Any) -> Any:
    """Apply all post-base DCOIR configuration exactly once."""

    _apply_adversarial_confirmation(config, data, hardened)
    _apply_semantic_adjudication(config, data, hardened)
    _apply_candidate_escalation(config, data, hardened)
    _apply_publication_and_context(config, data, hardened)
    _apply_per_file_routing(config, data)
    _initialize_run_telemetry_fail_soft(config)
    _apply_repair_critic_batching(config, data, hardened)
    return config
