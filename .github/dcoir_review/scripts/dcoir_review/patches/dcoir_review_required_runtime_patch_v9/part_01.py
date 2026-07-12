"""Ninth required-coverage layer for DCOIR Review.

This connector-safe layer keeps the final reviewer boring and deterministic:
OpenRouter Auto prompt-engineering preflights are visible and enforced before
Pareto calls, inline comments do not carry model footers, selected comments must
match the semantic risk at their changed line, Python pickle sinks become
required-adjacent coverage when present, and validation snippets avoid fragile
quoting.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v2 as v2
import dcoir_review_required_runtime_patch_v3 as v3
import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v6 as v6
import dcoir_review_required_runtime_patch_v8 as v8

if not hasattr(v3, "_strip_fences") and hasattr(v2, "_strip_fences"):
    v3._strip_fences = v2._strip_fences

from dcoir_review_required_runtime_patch_v9_prompting import (
    PARETO_CALL_EVENTS,
    PROMPT_REVIEW_CALLS,
    PROMPT_REVIEW_EVENTS,
    PROMPT_REVIEW_FAILURES,
    _ensure_prompt_review,
    _normalize_inline_comment,
    _normalize_yaml_identifier,
    _prompt_review_problem,
    _patch_inline_comment,
    _patch_progress_comment,
    _patch_prompt_review_call_accounting,
    _patch_prompt_review_readback,
    _patch_target_call_accounting,
    _patch_validation_text,
    _record_prompt_review_call,
    _record_prompt_review_event,
    _record_target_call,
    _strip_footer,
)
from dcoir_review_required_runtime_patch_v9_core import (
    PS_DYNAMIC_EXEC,
    PYTHON_PICKLE_LOAD,
    SELECTION_SUMMARY,
    _claim_text,
    _claimed_kinds,
    _confidence,
    _dedupe,
    _expected_by_line,
    _key_text,
    _line_kind,
    _line_number,
    _normalize,
    _postable_key,
    _quote_ps_string,
    _required_sentinels,
    _rewrite_validation,
    _semantic_kind,
    _semantic_mismatch,
    _sentinel_key,
    _severity_rank,
    _spare_priority,
    _validation_for_key,
    _yaml_load_arg,
)
from dcoir_review_required_runtime_patch_v9_selection import (
    _fallback_for_sentinel,
    _iter_added_diff_lines,
    _patch_pickle_sentinels,
    _patch_required_selection,
    _patch_yaml_safe_load_note,
    _select_required_postable,
)


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_yaml_safe_load_note()
    _patch_prompt_review_call_accounting()
    if base is not None:
        _patch_inline_comment(base)
        _patch_validation_text(base)
        _patch_progress_comment(base, hardened)
    if hardened is not None and base is not None:
        _patch_target_call_accounting(hardened)
        _patch_prompt_review_readback(hardened, base)
    _patch_pickle_sentinels(module, hardened)
    if hardened is not None:
        _patch_pickle_sentinels(hardened)
        _patch_required_selection(module, hardened)
