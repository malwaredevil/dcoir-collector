"""Canonical owner for final DCOIR inline finding/comment rendering.

Historical runtime layers repeatedly replaced ``base.build_inline_comment``. The
production-observable chain is now composed directly here: deterministic sentinel
canonicalization, repair rendering, verified ordinary rendering, safe native
suggestions, and the v16 deterministic base renderer. Earlier renderer generations
were superseded by v16 and no longer install runtime wrappers.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import repair_pipeline
from dcoir_review import verified_finding_render
import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v20 as v20
import dcoir_review_required_runtime_patch_v30 as v30


APPLIED_MARKER = "_dcoir_finding_comment_render_applied"


def _canonicalize_deterministic_sentinel(finding: dict[str, Any]) -> dict[str, Any]:
    kind = v30._deterministic_sentinel_kind(finding)
    if not kind:
        return finding
    item = dict(finding)
    title, body, _notes = v20._template_for_kind(kind)
    item["title"] = str(title or item.get("title", "") or "DCOIR Review finding").strip()
    item["body"] = str(body or item.get("body", "") or "").strip()
    return item


def _render_legacy_base_with_safe_suggestion(base: Any, finding: dict[str, Any]) -> str:
    rendered = str(v16._render_comment(finding) or "").rstrip()
    if "```suggestion" in rendered:
        return rendered
    suggestion = v20._safe_single_line_suggestion(base, finding)
    if not suggestion:
        return rendered
    return f"{rendered}\n\n```suggestion\n{suggestion}\n```".strip()


def render_inline_comment(module: Any, finding: dict[str, Any], model_used: str, config: Any) -> str:
    del model_used
    base = module.base
    item = _canonicalize_deterministic_sentinel(finding)
    if isinstance(item.get(repair_pipeline.REPAIR_MARKER), dict):
        return repair_pipeline._render_repair(module, item, config)
    if verified_finding_render._is_verified_ordinary_finding(item):
        return verified_finding_render._render_verified_ordinary(base, item, config)
    return _render_legacy_base_with_safe_suggestion(base, item)


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    base = getattr(module, "base", None)
    if base is None:
        raise RuntimeError("DCOIR canonical finding-comment renderer requires the base review module")

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        return render_inline_comment(module, finding, model_used, config)

    base.build_inline_comment = build_inline_comment
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "apply_pareto_context_module", "render_inline_comment"]
