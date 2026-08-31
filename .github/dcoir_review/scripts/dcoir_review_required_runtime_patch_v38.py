"""DCOIR Review v38 repair-author contract hardening.

A live blind issue-456 run proved that v37 preserves semantic findings through
publication, but all three verified repairs failed before the independent critic
because the repair author omitted the non-semantic per-edit ``purpose`` field.
Two otherwise exact repairs also carried author confidence below v36's 0.90
pre-critic cutoff, while one omitted confidence entirely.

v38 keeps every structural and exact-head repair safety check, but makes the
repair author a proposal source rather than a semantic acceptance authority:

* the prompt explicitly requires every repair-set field, including ``purpose``
  and numeric ``confidence``;
* a missing/blank ``purpose`` on an otherwise structurally valid edit is filled
  with deterministic explanatory metadata derived from the verified finding;
* missing author confidence is recorded as 0.0 rather than invented;
* author confidence is advisory and no longer vetoes an exact repair before the
  independent critic can inspect it; and
* the independent cross-family critic becomes the hard semantic gate at 0.95.

No path, line range, original block, replacement block, exact-head match, syntax,
edit-count, diff-anchor, or branch-write rule is relaxed. v38 never writes to the
reviewed pull-request branch.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v36 as v36


VERSION = "v38"
APPLIED_MARKER = "_dcoir_review_v38_applied"
PROMPT_STORAGE = "_dcoir_review_v38_original_repair_author_prompt"
PARSE_STORAGE = "_dcoir_review_v38_original_parse_author"
CRITIC_PROMPT_STORAGE = "_dcoir_review_v38_original_repair_critic_prompt"
CRITIC_MIN_CONFIDENCE = 0.95
AUTHOR_MIN_CONFIDENCE = 0.0


def _purpose_fallback(finding: dict[str, Any]) -> str:
    title = str(finding.get("title", "") or "").strip()
    if title:
        return f"Repair verified finding: {title}"[:600]
    path = str(finding.get("path", "") or "").strip()
    line = finding.get("line", 0)
    return f"Repair verified finding at {path}:{line}"[:600]


def _normalize_author_metadata(result: Any, finding: dict[str, Any]) -> Any:
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


def _patch_repair_author_contract() -> None:
    original_prompt = getattr(v36, PROMPT_STORAGE, None)
    if original_prompt is None:
        original_prompt = getattr(v36, "_repair_author_prompt", None)
        if callable(original_prompt):
            setattr(v36, PROMPT_STORAGE, original_prompt)
    if not callable(original_prompt):
        raise RuntimeError("DCOIR v38 could not locate v36 repair-author prompt")

    original_parse = getattr(v36, PARSE_STORAGE, None)
    if original_parse is None:
        original_parse = getattr(v36, "_parse_author", None)
        if callable(original_parse):
            setattr(v36, PARSE_STORAGE, original_parse)
    if not callable(original_parse):
        raise RuntimeError("DCOIR v38 could not locate v36 repair-author parser")

    original_critic_prompt = getattr(v36, CRITIC_PROMPT_STORAGE, None)
    if original_critic_prompt is None:
        original_critic_prompt = getattr(v36, "_repair_critic_prompt", None)
        if callable(original_critic_prompt):
            setattr(v36, CRITIC_PROMPT_STORAGE, original_critic_prompt)
    if not callable(original_critic_prompt):
        raise RuntimeError("DCOIR v38 could not locate v36 repair-critic prompt")

    def _repair_author_prompt(
        module: Any,
        finding: dict[str, Any],
        primary_file_text: str,
        pr_diff: str,
        head_sha: str,
        config: Any,
    ) -> str:
        base_prompt = original_prompt(module, finding, primary_file_text, pr_diff, head_sha, config)
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
""".rstrip()
        return base_prompt + contract

    def _parse_author(result: Any, finding: dict[str, Any], hardened: Any) -> dict[str, Any]:
        normalized = _normalize_author_metadata(result, finding)
        return original_parse(normalized, finding, hardened)

    def _repair_critic_prompt(
        module: Any,
        finding: dict[str, Any],
        author: dict[str, Any],
        file_cache: dict[str, str],
        config: Any,
    ) -> str:
        base_prompt = original_critic_prompt(module, finding, author, file_cache, config)
        contract = f"""

CRITIC ACCEPTANCE CONTRACT:
- ``accepted=true`` is a hard semantic authorization for human-applied repair
  publication and therefore requires confidence >= {CRITIC_MIN_CONFIDENCE:.2f}.
- Reject when confidence is lower, even if the repair is plausible.
- Author confidence is advisory only; independently validate the exact repair set.
""".rstrip()
        return base_prompt + contract

    v36._repair_author_prompt = _repair_author_prompt
    v36._parse_author = _parse_author
    v36._repair_critic_prompt = _repair_critic_prompt


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    # The repair author proposes; exact-head checks and the independent critic
    # decide whether the proposal is safe enough to publish.
    v36.AUTHOR_MIN_CONFIDENCE = AUTHOR_MIN_CONFIDENCE
    v36.CRITIC_MIN_CONFIDENCE = CRITIC_MIN_CONFIDENCE
    _patch_repair_author_contract()
    setattr(module, APPLIED_MARKER, True)
