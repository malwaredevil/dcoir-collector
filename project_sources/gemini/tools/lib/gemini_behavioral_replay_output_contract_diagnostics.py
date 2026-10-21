"""Optional scorer diagnostics for rendered analyst-visible response text.

This is not bundle-content validation, and these checks are not automatically
applied to every replay lane. That would create unreviewed false positives.
"""
from __future__ import annotations

import re
from typing import Any

from .gemini_behavioral_replay_text_scoring import duplicate_final_sections

# Narrow diagnostic-only internal keys. Broad terms "handoff" and
# "normalized evidence" can occur in legitimate analyst-facing prose.
INTERNAL_OUTPUT_KEYS = (
    "readiness_confirmed",
    "enterprise_web_search_status",
    "missing_minimum_evidence",
    "routing_state",
    "planner_payloads",
    "candidate_datasets",
    "output-composer",
    "command planning state",
)
SCAFFOLD_FENCE = re.compile(r"(?im)^[ \t]*\x60{3}(?:yaml|json)\b")
BLUF_SECTION = re.compile(r"(?im)^[ \t]*##[ \t]+(?:bluf|executive summary)[ \t]*$")


def analyze_visible_output(
    response_text: str, *, require_bluf_preamble: bool = False,
) -> dict[str, Any]:
    """Diagnose a response; section/preamble policy is fixture-opt-in."""
    text = str(response_text)
    lowered = text.lower()
    findings: list[str] = []
    details: dict[str, Any] = {}
    matched = [
        key for key in INTERNAL_OUTPUT_KEYS
        if re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", lowered)
    ]
    if matched:
        findings.append("internal_state_leakage")
        details["matched_internal_terms"] = matched
    scaffold_markers = [m.group(0).strip() for m in SCAFFOLD_FENCE.finditer(text)]
    if scaffold_markers:
        findings.append("yaml_or_json_scaffold")
        details["matched_scaffold_markers"] = scaffold_markers
    duplicate_headers = duplicate_final_sections(text)
    if duplicate_headers:
        findings.append("duplicate_final_sections")
        details["duplicate_headers"] = duplicate_headers
    if require_bluf_preamble:
        first = BLUF_SECTION.search(text)
        preamble = text[:first.start()].strip() if first else text.strip()
        if preamble or first is None or not text[first.end():].strip():
            findings.append("malformed_preamble")
            details["preamble_excerpt"] = preamble[:400]
    return {"accepted": not findings, "findings": sorted(findings), "details": details}
