"""v48 companion guard for the legacy prompt-review provider seam.

The main v48 overlay guards the canonical hardened provider request.  Historical
v6 prompt-review support can issue a separate provider request before that
canonical request when prompt review is enabled.  This companion keeps the same
exact-scope invariant around that direct request and, importantly, re-raises a
supersession after v6's deliberate prompt-review fallback catches provider
exceptions.  That prevents the target review request from starting after a head
move detected during prompt review.
"""

from __future__ import annotations

import importlib
from typing import Any

import dcoir_review_required_runtime_patch_v48 as v48


APPLIED_MARKER = "_dcoir_review_v48_prompt_guard_applied"


def patch_prompt_review_module(module: Any, prompt_module: Any) -> None:
    request_storage = "_dcoir_review_v48_prompt_original_request"
    original_request = getattr(prompt_module, request_storage, None)
    if original_request is None:
        original_request = getattr(prompt_module, "_request_prompt_review", None)
        if callable(original_request):
            setattr(prompt_module, request_storage, original_request)

    if callable(original_request):
        def guarded_request(original_prompt, prompt_kind, config, hardened, base):
            if v48._guard(module) is not None:
                v48.assert_current_review_scope(module, "prompt-review request", config)
            result = original_request(original_prompt, prompt_kind, config, hardened, base)
            if v48._guard(module) is not None:
                v48.assert_current_review_scope(module, "prompt-review response", config)
            return result

        prompt_module._request_prompt_review = guarded_request

    review_storage = "_dcoir_review_v48_prompt_original_review_once"
    original_review = getattr(prompt_module, review_storage, None)
    if original_review is None:
        original_review = getattr(prompt_module, "_review_prompt_once", None)
        if callable(original_review):
            setattr(prompt_module, review_storage, original_review)

    if callable(original_review):
        def guarded_review_once(original_prompt, config, hardened, base):
            if v48._guard(module) is not None:
                v48.assert_current_review_scope(module, "prompt-review stage", config)
            result = original_review(original_prompt, config, hardened, base)
            if v48._guard(module) is not None:
                # v6 intentionally falls back to the original prompt on provider
                # exceptions. If the direct-request guard was the exception, its
                # terminal state must win before the target provider call begins.
                v48.assert_current_review_scope(module, "prompt-review stage completion", config)
            return result

        prompt_module._review_prompt_once = guarded_review_once


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    prompt_module = importlib.import_module("dcoir_review_required_runtime_patch_v6")
    patch_prompt_review_module(module, prompt_module)
    setattr(module, APPLIED_MARKER, True)
