"""DCOIR Review v30 false-positive precision overlay for issue #449.

v30 addresses two coupled precision failures observed while reviewing PR #448:

1. the truthy-literal risk sentinel must distinguish a bare literal operand
   (``condition or "high"``) from a quoted literal that participates in a real
   comparison or membership expression (``condition or "x" not in values``);
2. the repair author needs an explicit, fail-closed way to say that the alleged
   defect is absent. A high-confidence defect-absent attestation suppresses the
   finding instead of publishing a self-contradictory "no safe fix" comment.

A real finding that simply lacks a safe one-line repair is still published.
Native GitHub suggestions remain human-applied only; this overlay performs no
pull-request branch writes or autonomous remediation.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import dcoir_review_required_runtime_patch_v25 as v25
import dcoir_review_required_runtime_patch_v28 as v28


VERSION = "v30"
APPLIED_MARKER = "_dcoir_review_v30_applied"
SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE = 0.95
SUPPRESSED_OUTCOME = "defect-absent-suppressed"

# A coarse sentinel may first recognize ``or <quoted literal>``. This tail guard
# prevents the literal from being classified as a bare truthy operand when it
# is actually the left operand of a comparison/membership expression.
_COMPARISON_TAIL = (
    r"(?:"
    r"(?:not\s+in|in|is\s+not|is)\b"
    r"|==|!=|<=|>=|<|>"
    r"|-(?:eq|ne|lt|le|gt|ge|like|notlike|match|notmatch|contains|notcontains|in|notin|is|isnot)\b"
    r")"
)
TRUTHY_LITERAL_BRANCH_PATTERN = re.compile(
    r"^\s*(?:if|elif|elseif|while)\b[^\n]*(?:\bor\b|\b-or\b)\s+"
    r"(?P<quote>['\"])[^'\"]+(?P=quote)(?!\s*" + _COMPARISON_TAIL + r")",
    re.IGNORECASE,
)


def _patch_truthy_literal_rule(module: Any) -> None:
    patched = []
    replaced = False
    for label, detail, pattern in tuple(module.RISK_SENTINEL_RULES):
        if label == "truthy literal branch condition":
            patched.append((label, detail, TRUTHY_LITERAL_BRANCH_PATTERN))
            replaced = True
        else:
            patched.append((label, detail, pattern))
    if not replaced:
        raise RuntimeError("DCOIR v30 could not locate the truthy-literal risk-sentinel rule")
    module.RISK_SENTINEL_RULES = tuple(patched)


def _patch_author_schema() -> None:
    schema = copy.deepcopy(v25.REPAIR_AUTHOR_SCHEMA)
    required = list(schema.get("required") or [])
    if "defect_present" not in required:
        required.insert(0, "defect_present")
    properties = dict(schema.get("properties") or {})
    properties["defect_present"] = {"type": "boolean"}
    schema["required"] = required
    schema["properties"] = properties
    v25.REPAIR_AUTHOR_SCHEMA = schema


def _author_prompt(original_prompt: Any, module: Any, finding: dict[str, Any], path: str, line: int, current_line: str, file_text: str, config: Any) -> str:
    prompt = original_prompt(module, finding, path, line, current_line, file_text, config)
    addendum = """

Defect-presence gate (mandatory):
- Independently verify whether the alleged defect actually exists in the exact
  anchored line and full head-file context, even though an earlier verifier
  supported the candidate.
- Set `defect_present` to true only when the evidence still proves the defect.
- Set `defect_present` to false only when the exact code/context proves the
  allegation is absent or semantically inapplicable.
- `defect_present=false` is NOT a substitute for `no_safe_single_line_fix`.
  If the defect is real but needs multiple lines/files or has no safe exact
  one-line repair, keep `defect_present=true`, choose
  `no_safe_single_line_fix`, and explain why.
- When `defect_present=false`, choose `no_safe_single_line_fix`, return an empty
  replacement, and explain the concrete evidence that disproves the finding.
""".rstrip()
    return v25._sanitize_prompt(module, prompt + addendum, config)


def _author_result(original_author_result: Any, result: Any, finding: dict[str, Any], path: str, line: int, hardened: Any) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("defect_present"), bool):
        raise hardened.ReviewQualityError("DCOIR repair author omitted boolean defect_present attestation")
    parsed = original_author_result(result, finding, path, line, hardened)
    parsed["defect_present"] = bool(result["defect_present"])
    if not parsed["defect_present"]:
        parsed["action"] = "no_safe_single_line_fix"
        parsed["replacement"] = ""
    return parsed


def _declined_item(original_declined_item: Any, finding: dict[str, Any], path: str, line: int, reason: str, *, author: dict[str, Any] | None = None, author_model: str = "", author_tier: str = "", outcome: str = "no-safe-single-line-fix") -> dict[str, Any]:
    defect_absent = bool(author and author.get("defect_present") is False)
    confidence = float(author.get("confidence", 0) or 0) if author else 0.0
    if defect_absent and confidence >= SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE:
        item = original_declined_item(
            finding,
            path,
            line,
            reason,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
            outcome=SUPPRESSED_OUTCOME,
        )
        marker = item.get(v25.REPAIR_MARKER) if isinstance(item.get(v25.REPAIR_MARKER), dict) else {}
        marker.update(
            {
                "version": VERSION,
                "outcome": SUPPRESSED_OUTCOME,
                "defect_present": False,
                "defect_presence_confidence": confidence,
            }
        )
        item[v25.REPAIR_MARKER] = marker
        return item

    # Fail closed when absence confidence is insufficient: retain the original
    # verified finding instead of publishing author wording that says no defect.
    safe_author = author if not defect_absent else None
    item = original_declined_item(
        finding,
        path,
        line,
        reason,
        author=safe_author,
        author_model=author_model,
        author_tier=author_tier,
        outcome=outcome,
    )
    marker = item.get(v25.REPAIR_MARKER) if isinstance(item.get(v25.REPAIR_MARKER), dict) else {}
    marker["version"] = VERSION
    if defect_absent:
        marker.update(
            {
                "defect_present": False,
                "defect_presence_confidence": confidence,
                "suppression_declined": "defect-absence confidence below threshold",
            }
        )
    item[v25.REPAIR_MARKER] = marker
    return item


def filter_suppressed_findings(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    suppressed = 0
    for item in findings:
        marker = item.get(v25.REPAIR_MARKER) if isinstance(item.get(v25.REPAIR_MARKER), dict) else {}
        if marker.get("outcome") == SUPPRESSED_OUTCOME:
            suppressed += 1
            continue
        kept.append(item)
    return kept, suppressed


def apply_pareto_context_module(module: Any) -> None:
    # Selftests and composite harnesses can reuse one imported review module in
    # a process. Do not stack prompt/parser/synthesis wrappers on repeated apply.
    if getattr(module, APPLIED_MARKER, False):
        return

    _patch_truthy_literal_rule(module)
    _patch_author_schema()

    original_prompt = v25._repair_author_prompt
    original_author_result = v28._author_result
    original_declined_item = v28._declined_item
    original_synthesize = module.synthesize_fixes_for_findings

    v25._repair_author_prompt = lambda mod, finding, path, line, current_line, file_text, config: _author_prompt(
        original_prompt, mod, finding, path, line, current_line, file_text, config
    )
    v28._author_result = lambda result, finding, path, line, hardened: _author_result(
        original_author_result, result, finding, path, line, hardened
    )
    v28._declined_item = lambda finding, path, line, reason, *, author=None, author_model="", author_tier="", outcome="no-safe-single-line-fix": _declined_item(
        original_declined_item,
        finding,
        path,
        line,
        reason,
        author=author,
        author_model=author_model,
        author_tier=author_tier,
        outcome=outcome,
    )

    def synthesize_fixes_for_findings(
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        repaired = original_synthesize(findings, gh, pr, schema, config, reporter)
        kept, suppressed = filter_suppressed_findings(repaired)
        if suppressed and reporter is not None:
            reporter.update(
                "repair-v30",
                f"suppressed {suppressed} high-confidence finding(s) after explicit defect-absent attestation",
            )
        return kept

    module.synthesize_fixes_for_findings = synthesize_fixes_for_findings
    setattr(module, APPLIED_MARKER, True)
