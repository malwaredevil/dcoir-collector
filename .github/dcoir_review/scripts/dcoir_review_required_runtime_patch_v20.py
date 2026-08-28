"""DCOIR Review v20 selection/suggestion compatibility overlay.

This overlay repairs two production-runtime seams exposed by the controlled
#436 live validation PR:

1. the hardened reviewer can detect the generic ``truthy literal branch
   condition`` sentinel, but the older v16 required-coverage selector predates
   that sentinel and can drop it before publication; and
2. the v16 final inline renderer predates independent fix synthesis and does
   not render a verified ``suggested_replacement`` as a GitHub native
   ``suggestion`` fence.

The overlay does not add branch-write capability. Detector-authored suggestion
text remains untrusted: the renderer only emits a native suggestion when the
post-v19 independent fix-synthesis result is marked here as verified.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16


VERSION = "v20"
PYTHON_TRUTHY_LITERAL_BRANCH = "python_truthy_literal_branch"
SYNTHESIS_VERIFIED_MARKER = "_dcoir_fix_synthesis_verified_v20"

TRUTHY_LITERAL_BRANCH_RE = re.compile(
    r"^\s*(?:if|elif|while)\b[^\n]*(?:\bor\b)\s+['\"][^'\"]+['\"]",
    re.IGNORECASE,
)

_ORIGINAL_V16_LINE_KIND = v16._line_kind
_ORIGINAL_V16_TEMPLATE_FOR_KIND = v16._template_for_kind
_ORIGINAL_V16_KIND_RANK = v16._kind_rank


def _line_kind(path: str, text: str) -> str:
    if Path(str(path or "").lower()).suffix == ".py" and TRUTHY_LITERAL_BRANCH_RE.search(str(text or "")):
        return PYTHON_TRUTHY_LITERAL_BRANCH
    return _ORIGINAL_V16_LINE_KIND(path, text)


def _template_for_kind(kind: str) -> tuple[str, str, str]:
    if kind == PYTHON_TRUTHY_LITERAL_BRANCH:
        return (
            "Python branch condition contains an always-truthy literal",
            "A non-empty string literal after `or` is always truthy, so this branch bypasses the intended comparison.",
            "Compare the same variable explicitly against the second allowed value instead of using the bare string literal.",
        )
    return _ORIGINAL_V16_TEMPLATE_FOR_KIND(kind)


def _kind_rank(kind: str) -> int:
    if kind == PYTHON_TRUTHY_LITERAL_BRANCH:
        return 17
    return _ORIGINAL_V16_KIND_RANK(kind)


def _patch_v16_selection_registry() -> None:
    """Teach the active v16 selector about a sentinel added after v16 shipped."""
    v16.CORE_REQUIRED_KINDS.add(PYTHON_TRUTHY_LITERAL_BRANCH)
    v16.TRACKED_KINDS.add(PYTHON_TRUTHY_LITERAL_BRANCH)
    v16._line_kind = _line_kind
    v16._template_for_kind = _template_for_kind
    v16._kind_rank = _kind_rank


def _safe_single_line_suggestion(base: Any, finding: dict[str, Any]) -> str:
    if not bool(finding.get(SYNTHESIS_VERIFIED_MARKER)):
        return ""
    suggestion = str(finding.get("suggested_replacement", "") or "").rstrip()
    if not suggestion or any(marker in suggestion for marker in ("\n", "\r", "```", "~~~")):
        return ""
    if len(suggestion) > 1000:
        return ""
    checker = getattr(base, "is_safe_suggestion", None)
    if callable(checker) and not checker(suggestion):
        return ""
    return suggestion


def _mark_independent_synthesis_results(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark only suggestions that survived the already-run independent synthesis pass."""
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        suggestion = str(finding.get("suggested_replacement", "") or "").strip()
        if suggestion:
            finding[SYNTHESIS_VERIFIED_MARKER] = True
        else:
            finding.pop(SYNTHESIS_VERIFIED_MARKER, None)
    return findings


def _patch_synthesis_provenance(module: Any) -> None:
    storage = "_dcoir_required_v20_original_synthesize_fixes_for_findings"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "synthesize_fixes_for_findings", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        return

    def synthesize_fixes_for_findings(
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        enriched = original(findings, gh, pr, schema, config, reporter)
        return _mark_independent_synthesis_results(enriched)

    module.synthesize_fixes_for_findings = synthesize_fixes_for_findings


def _patch_native_suggestion_renderer(module: Any) -> None:
    base = getattr(module, "base", None)
    if base is None:
        return
    storage = "_dcoir_required_v20_original_build_inline_comment"
    original = getattr(base, storage, None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        if callable(original):
            setattr(base, storage, original)
    if not callable(original):
        return

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        rendered = str(original(finding, model_used, config) or "").rstrip()
        if "```suggestion" in rendered:
            return rendered
        suggestion = _safe_single_line_suggestion(base, finding)
        if not suggestion:
            return rendered
        return f"{rendered}\n\n```suggestion\n{suggestion}\n```".strip()

    base.build_inline_comment = build_inline_comment


def apply_pareto_context_module(module: Any) -> None:
    _patch_v16_selection_registry()
    _patch_synthesis_provenance(module)
    _patch_native_suggestion_renderer(module)
