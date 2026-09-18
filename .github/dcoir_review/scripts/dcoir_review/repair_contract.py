"""Stable DCOIR Review repair-author/critic contract policy.

This owner contains the v38 repair contract as pure policy helpers. The active
v36 repair stage calls these helpers directly, so no prompt/parser callable is
stored or replaced at runtime.
"""

from __future__ import annotations

from typing import Any


APPLIED_MARKER = "_dcoir_review_repair_contract_applied"
CRITIC_MIN_CONFIDENCE = 0.95
AUTHOR_MIN_CONFIDENCE = 0.0


def _purpose_fallback(finding: dict[str, Any]) -> str:
    title = str(finding.get("title", "") or "").strip()
    if title:
        return f"Repair verified finding: {title}"[:600]
    path = str(finding.get("path", "") or "").strip()
    line = finding.get("line", 0)
    return f"Repair verified finding at {path}:{line}"[:600]


def normalize_author_metadata(result: Any, finding: dict[str, Any]) -> Any:
    """Normalize only non-semantic author metadata; never repair edit structure."""

    if not isinstance(result, dict):
        return result

    normalized = dict(result)
    if normalized.get("confidence") is None:
        normalized["confidence"] = 0.0

    if str(normalized.get("action", "") or "").strip() != "repair_set":
        return normalized

    raw_edits = normalized.get("edits")
    if not isinstance(raw_edits, list):
        return normalized

    fallback = _purpose_fallback(finding)
    edits: list[Any] = []
    for raw in raw_edits:
        if not isinstance(raw, dict):
            edits.append(raw)
            continue
        edit = dict(raw)
        if not str(edit.get("purpose", "") or "").strip():
            edit["purpose"] = fallback
        edits.append(edit)
    normalized["edits"] = edits
    return normalized


def append_author_contract(base_prompt: str) -> str:
    contract = f"""
REQUIRED OUTPUT CONTRACT (do not omit fields):
- Return one object with exactly these top-level semantic fields:
  defect_present, action, edits, confidence, display_title, display_body,
  rationale, validation.
- ``confidence`` MUST always be a numeric value from 0.0 through 1.0. It is the
  repair author's confidence in its proposal; it is recorded for diagnostics and
  does not replace the independent critic.
- When action=repair_set, EVERY edit MUST contain all six fields:
  path, start_line, end_line, original, replacement, purpose.
- ``purpose`` MUST be a short non-empty explanation of why that exact edit is
  necessary for this verified root cause. It is explanatory metadata, not a place
  to add extra edits or requirements.
- Never omit an edit field merely because its value seems obvious from the finding.
- If any structural repair field cannot be stated exactly from supplied evidence,
  use action=no_safe_repair and edits=[].
- An accepted repair still must pass exact-head deterministic validation and an
  independent cross-family critic at confidence >= {CRITIC_MIN_CONFIDENCE:.2f}.
""".strip()
    return f"{base_prompt}\n\n{contract}"


def append_critic_contract(base_prompt: str) -> str:
    contract = f"""
CRITIC ACCEPTANCE CONTRACT:
- ``accepted=true`` is a hard semantic authorization for human-applied repair
  publication and therefore requires confidence >= {CRITIC_MIN_CONFIDENCE:.2f}.
- ``confidence`` MUST be numeric and remain within 0.0 through 1.0.
- Reject when confidence is lower, even if the repair is plausible.
- Author confidence is advisory only; independently validate the exact repair set.
""".strip()
    return f"{base_prompt}\n\n{contract}"


def validated_critic_confidence(result: Any, hardened: Any) -> float:
    """Return bounded critic confidence or fail closed on schema drift."""

    if not isinstance(result, dict):
        raise hardened.ReviewQualityError("DCOIR repair-set critic returned a non-object result")
    raw_confidence = result.get("confidence", 0)
    if isinstance(raw_confidence, bool):
        raise hardened.ReviewQualityError("DCOIR repair-set critic returned boolean confidence")
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError) as exc:
        raise hardened.ReviewQualityError("DCOIR repair-set critic returned invalid confidence") from exc
    if not 0.0 <= confidence <= 1.0:
        raise hardened.ReviewQualityError("DCOIR repair-set critic confidence was outside 0.0..1.0")
    return confidence


def apply_pareto_context_module(module: Any) -> None:
    """Compatibility registration only; production composition is explicit."""

    setattr(module, APPLIED_MARKER, True)
