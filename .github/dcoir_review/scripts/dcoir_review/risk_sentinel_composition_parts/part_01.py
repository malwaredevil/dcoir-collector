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

import dcoir_review.required_coverage_primitives as v2
import dcoir_review.risk_sentinel_identity as v3
from dcoir_review import risk_sentinel_taxonomy as _v4
from dcoir_review import risk_sentinel_policy as _v5
from dcoir_review import prompt_review_policy as _v6
from dcoir_review import selection_pressure_policy as _v8
import importlib

# Historical v9 compatibility aliases; canonical implementation remains stable-owner based.
v4 = _v4
v5 = _v5
v6 = _v6
v8 = _v8

v9_core = importlib.import_module("dcoir_review.risk_sentinel_state")

if not hasattr(v3, "_strip_fences") and hasattr(v2, "_strip_fences"):
    v3._strip_fences = v2._strip_fences

from dcoir_review import prompt_review_diagnostics_helpers as _prompt_diag
from dcoir_review.prompt_review_diagnostics_helpers import (
    _patch_progress_comment,
    _patch_prompt_review_call_accounting,
    _patch_prompt_review_readback,
    _patch_target_call_accounting,
)

# Historical v9 compatibility exports remain explicit aliases to the stable owner.
PARETO_CALL_EVENTS = _prompt_diag.PARETO_CALL_EVENTS
PROMPT_REVIEW_CALLS = _prompt_diag.PROMPT_REVIEW_CALLS
PROMPT_REVIEW_EVENTS = _prompt_diag.PROMPT_REVIEW_EVENTS
PROMPT_REVIEW_FAILURES = _prompt_diag.PROMPT_REVIEW_FAILURES
_ensure_prompt_review = _prompt_diag._ensure_prompt_review
_normalize_inline_comment = _prompt_diag._normalize_inline_comment
_normalize_yaml_identifier = _prompt_diag._normalize_yaml_identifier
_prompt_review_problem = _prompt_diag._prompt_review_problem
_record_prompt_review_call = _prompt_diag._record_prompt_review_call
_record_prompt_review_event = _prompt_diag._record_prompt_review_event
_record_target_call = _prompt_diag._record_target_call
_strip_footer = _prompt_diag._strip_footer
PS_DYNAMIC_EXEC = v9_core.PS_DYNAMIC_EXEC
PYTHON_PICKLE_LOAD = v9_core.PYTHON_PICKLE_LOAD
SELECTION_SUMMARY = v9_core.SELECTION_SUMMARY
_claim_text = v9_core._claim_text
_claimed_kinds = v9_core._claimed_kinds
_confidence = v9_core._confidence
_dedupe = v9_core._dedupe
_expected_by_line = v9_core._expected_by_line
_key_text = v9_core._key_text
_line_number = v9_core._line_number
_normalize = v9_core._normalize
_postable_key = v9_core._postable_key
_quote_ps_string = v9_core._quote_ps_string
_required_sentinels = v9_core._required_sentinels
_rewrite_validation = v9_core._rewrite_validation
_semantic_mismatch = v9_core._semantic_mismatch
_sentinel_key = v9_core._sentinel_key
_severity_rank = v9_core._severity_rank
_spare_priority = v9_core._spare_priority
_validation_for_key = v9_core._validation_for_key
_yaml_load_arg = v9_core._yaml_load_arg


def __getattr__(name: str) -> Any:
    # Classifier hooks are mutable runtime seams. Delegate reads to v9_core
    # until a later compatibility layer explicitly overrides the v9 export.
    if name in {"_line_kind", "_semantic_kind"}:
        return getattr(v9_core, name)
    raise AttributeError(name)


from dcoir_review import risk_sentinel_selection_support as _selection_support
from dcoir_review.risk_sentinel_selection_support import (
    _patch_pickle_sentinels,
    _patch_required_selection,
    _patch_yaml_safe_load_note,
)

_fallback_for_sentinel = _selection_support._fallback_for_sentinel
_iter_added_diff_lines = _selection_support._iter_added_diff_lines
_select_required_postable = _selection_support._select_required_postable


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_yaml_safe_load_note()
    _patch_prompt_review_call_accounting()
    if base is not None:
        _patch_progress_comment(base, hardened)
    if hardened is not None and base is not None:
        _patch_target_call_accounting(hardened)
        _patch_prompt_review_readback(hardened, base)
    _patch_pickle_sentinels(module, hardened)
    if hardened is not None:
        _patch_pickle_sentinels(hardened)
        _patch_required_selection(module, hardened)
