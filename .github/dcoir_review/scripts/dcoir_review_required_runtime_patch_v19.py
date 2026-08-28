"""DCOIR Review v19 quality overlay.

This narrow overlay advances #433 and #434 without granting DCOIR Review any
branch-write capability. It:

- records whether each post-synthesis finding received a native GitHub
  suggestion, fallback guidance, or no repair proposal; and
- fails closed when the independent fix-synthesis pass explicitly contradicts
  the detector by calling the finding a false positive, recommending dismissal,
  or saying no code change is warranted.

The contradiction path intentionally does not silently turn the review clean.
The existing terminal-failure reporter makes the quality failure visible on the
pull request so an operator can disposition it.
"""

from __future__ import annotations

import re
from typing import Any


VERSION = "v19"
OUTCOME_ARTIFACT = "metadata/fix-synthesis-outcomes-v19.json"

SELF_DISQUALIFYING_FIX_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:appears?|is|looks)\s+(?:to\s+be\s+)?(?:a\s+)?false\s+positive\b", re.IGNORECASE),
        "fix synthesis calls the finding a false positive",
    ),
    (
        re.compile(
            r"\bshould\s+(?:be\s+)?(?:dispositioned|dismissed)\b.{0,120}\brather\s+than\s+(?:modified|changed|fixed)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "fix synthesis recommends dismissal instead of a code change",
    ),
    (
        re.compile(
            r"\bno\s+(?:code\s+)?change\s+(?:is\s+)?(?:warranted|required|needed|necessary)\b",
            re.IGNORECASE,
        ),
        "fix synthesis says no code change is warranted",
    ),
)


def _fix_guidance_text(finding: dict[str, Any]) -> str:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    return "\n".join(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))


def fix_synthesis_self_disqualification_reason(finding: dict[str, Any]) -> str:
    """Return a bounded contradiction reason derived only from fix-synthesis guidance."""
    text = _fix_guidance_text(finding)
    if not text.strip():
        return ""
    for pattern, reason in SELF_DISQUALIFYING_FIX_PATTERNS:
        if pattern.search(text):
            return reason
    return ""


def repair_outcome(finding: dict[str, Any]) -> str:
    suggestion = str(finding.get("suggested_replacement", "") or "").strip()
    if suggestion:
        return "native-suggestion"
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if any(str(guidance.get(key, "") or "").strip() for key in ("remove", "replace", "add", "notes")):
        return "fallback-guidance"
    return "none"


def _outcome_rows(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for finding in findings:
        try:
            line = int(finding.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        rows.append(
            {
                "path": str(finding.get("path", "") or ""),
                "line": line,
                "title": str(finding.get("title", "") or "")[:120],
                "outcome": repair_outcome(finding),
                "self_disqualification_reason": fix_synthesis_self_disqualification_reason(finding),
            }
        )
    return rows


def _write_outcomes(module: Any, config: Any, findings: list[dict[str, Any]]) -> None:
    hardened = getattr(module, "hardened", None)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None) if hardened is not None else None
    if callable(writer):
        rows = _outcome_rows(findings)
        writer(
            config,
            OUTCOME_ARTIFACT,
            {
                "version": VERSION,
                "finding_count": len(rows),
                "native_suggestion_count": sum(row["outcome"] == "native-suggestion" for row in rows),
                "fallback_guidance_count": sum(row["outcome"] == "fallback-guidance" for row in rows),
                "no_repair_count": sum(row["outcome"] == "none" for row in rows),
                "self_disqualified_count": sum(bool(row["self_disqualification_reason"]) for row in rows),
                "findings": rows,
            },
        )


def _patch_fix_synthesis_collection(module: Any) -> None:
    storage = "_dcoir_required_v19_original_synthesize_fixes_for_findings"
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
        _write_outcomes(module, config, enriched)
        contradictions = [
            (finding, fix_synthesis_self_disqualification_reason(finding))
            for finding in enriched
            if fix_synthesis_self_disqualification_reason(finding)
        ]
        if not contradictions:
            return enriched

        locations = []
        for finding, reason in contradictions[:4]:
            path = str(finding.get("path", "") or "<missing-path>")
            try:
                line = int(finding.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            locations.append(f"{path}:{line or '<missing-line>'} ({reason})")
        detail = "; ".join(locations)
        update = getattr(reporter, "update", None)
        if callable(update):
            update("fix-synthesis", f"quality contradiction in {len(contradictions)} finding(s); refusing to publish")
        error_type = getattr(getattr(module, "hardened", None), "ReviewQualityError", RuntimeError)
        raise error_type(
            "DCOIR Review quality failure: the independent fix-synthesis pass contradicted "
            f"{len(contradictions)} detector finding(s), so the reviewer refused to publish self-contradictory findings. "
            f"Contradictions: {detail}."
        )

    module.synthesize_fixes_for_findings = synthesize_fixes_for_findings


def apply_pareto_context_module(module: Any) -> None:
    _patch_fix_synthesis_collection(module)
