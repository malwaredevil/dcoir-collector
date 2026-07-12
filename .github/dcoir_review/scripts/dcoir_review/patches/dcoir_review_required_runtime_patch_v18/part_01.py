"""Eighteenth DCOIR Review calibration overlay.

v18 is a narrow post-v17 cleanup layer for the #344 grading defects. It does
not change v16/v17 required coverage selection. It only:

- strips internal fix-synthesis/schema language from normalized/postable
  dynamic-exec guidance while preserving the raw guidance in debug artifacts;
- carries covered-sentinel source text into aggregate comments; and
- makes aggregate-covered Run-key persistence visible as HKCU/HKLM Run-key
  persistence in human-facing review output.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16


VERSION = "v18"

INTERNAL_FIX_SYNTHESIS_RE = re.compile(
    r"\b(?:"
    r"required\s+['\"]?finding_id['\"]?\s+field\s+is\s+missing|"
    r"missing\s+['\"]?finding_id['\"]?|"
    r"supplied\s+finding|"
    r"no\s+anchored\s+repair\s+can\s+be\s+synthesized"
    r")\b",
    re.IGNORECASE,
)

DYNAMIC_EXEC_NOTES = (
    "Remove the dynamic execution or replace it with a non-executing parser, "
    "constrained AST allowlist, or explicit allowlist. Do not replace eval or "
    "exec with another dynamic execution primitive."
)
GENERIC_INTERNAL_SYNTHESIS_NOTES = (
    "No exact code replacement is provided for this finding. Apply a targeted fix "
    "for the observed issue and run the listed validation after the change."
)
FINDING_TEXT_FIELDS = ("title", "body", "suggested_replacement", "validation")
GUIDANCE_TEXT_FIELDS = (
    "notes",
    "remove",
    "replace",
    "add",
    "validation",
    "remove_code",
    "replace_code",
    "add_code",
)


def _preserve(module: Any, name: str) -> Any:
    storage = f"_dcoir_required_v18_original_{name.lstrip('_')}"
    original = getattr(module, storage, None)
    if callable(original):
        return original
    current = getattr(module, name)
    setattr(module, storage, current)
    return current


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _key_tuple(raw: Any) -> v16.SentinelKey | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or "")
    return None


def _key_id(key: v16.SentinelKey) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def _line_text_from_finding(finding: dict[str, Any]) -> str:
    return str(
        finding.get("_anchored_line_text")
        or finding.get("text")
        or finding.get("line_text")
        or ""
    )


def _language_hint(path: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    return {
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _guidance_with_notes(finding: dict[str, Any], notes: str) -> dict[str, str]:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    language = str(guidance.get("language") or _language_hint(str(finding.get("path", "") or "")))
    return {"language": language, "notes": notes}


def _internal_fix_synthesis_leak(value: Any) -> bool:
    return bool(INTERNAL_FIX_SYNTHESIS_RE.search(str(value or "")))


def _raw_posted_fields(finding: dict[str, Any]) -> dict[str, Any]:
    raw: dict[str, Any] = {name: finding.get(name) for name in FINDING_TEXT_FIELDS if finding.get(name)}
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if guidance:
        raw["fix_guidance"] = {name: guidance.get(name) for name in GUIDANCE_TEXT_FIELDS if guidance.get(name)}
    return raw


def _finding_has_internal_leak(finding: dict[str, Any]) -> bool:
    for name in FINDING_TEXT_FIELDS:
        if _internal_fix_synthesis_leak(finding.get(name, "")):
            return True
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    for name in GUIDANCE_TEXT_FIELDS:
        if _internal_fix_synthesis_leak(guidance.get(name, "")):
            return True
    return False


def _run_key_hive(line_text: str) -> str:
    lower = str(line_text or "").lower()
    if "hkcu:" in lower or "hkey_current_user" in lower:
        return "HKCU"
    if "hklm:" in lower or "hkey_local_machine" in lower:
        return "HKLM"
    return "Windows"


def _covered_keys(finding: dict[str, Any]) -> list[v16.SentinelKey]:
    keys: list[v16.SentinelKey] = []
    raw_keys = finding.get("covered_risk_sentinel_keys")
    if isinstance(raw_keys, list):
        for raw in raw_keys:
            key = _key_tuple(raw)
            if key is not None:
                keys.append(key)
    return keys


def _covered_signal_text(finding: dict[str, Any], key: v16.SentinelKey) -> str:
    details = finding.get("_dcoir_v18_covered_signal_text")
    if isinstance(details, dict):
        return str(details.get(_key_id(key), "") or "")
    return ""


def _clean_dynamic_exec_guidance(finding: dict[str, Any], line_text: str) -> dict[str, str]:
    guidance = _guidance_with_notes(finding, DYNAMIC_EXEC_NOTES)
    if (
        line_text
        and Path(str(finding.get("path", "") or "").lower()).suffix == ".py"
        and not _internal_fix_synthesis_leak(line_text)
    ):
        guidance["remove"] = line_text
    return guidance


def _scrub_internal_fix_synthesis_leak(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    path, _line, kind = v16._postable_key(item)
    if not _finding_has_internal_leak(item):
        return item
    title, body, _notes = v16._template_for_kind(kind)
    if _internal_fix_synthesis_leak(item.get("title", "")):
        item["title"] = title
    if _internal_fix_synthesis_leak(item.get("body", "")):
        item["body"] = body
    if _internal_fix_synthesis_leak(item.get("validation", "")):
        item["validation"] = ""
    if kind == v16.PYTHON_DYNAMIC_EXEC:
        line_text = _line_text_from_finding(item)
        item["title"] = title
        item["body"] = body
        item["fix_guidance"] = _clean_dynamic_exec_guidance(item, line_text)
    else:
        item["fix_guidance"] = _guidance_with_notes(item, GENERIC_INTERNAL_SYNTHESIS_NOTES)
    item["suggested_replacement"] = ""
    item["_dcoir_v18_internal_fix_synthesis_suppressed"] = True
    item.setdefault("_risk_sentinel_key", [path, _line, kind])
    return item


def _aggregate_run_key_detail(finding: dict[str, Any]) -> tuple[str, int] | None:
    for key in _covered_keys(finding):
        if key[2] != v13.PS_RUN_KEY_PERSISTENCE:
            continue
        hive = _run_key_hive(_covered_signal_text(finding, key) or _line_text_from_finding(finding))
        return hive, key[1]
    return None


def _enrich_aggregate_run_key_output(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    _path, _line, kind = v16._postable_key(item)
    detail = _aggregate_run_key_detail(item)
    if detail is None or kind == v13.PS_RUN_KEY_PERSISTENCE:
        return item
    hive, run_key_line = detail
    phrase = (
        f"Covered Run-key signal: line {run_key_line} writes {hive} Run-key "
        "persistence and must be reviewed as a startup-persistence risk."
    )
    body = str(item.get("body", "") or "").strip()
    if "run-key" not in body.lower() or hive.lower() not in body.lower():
        item["body"] = f"{body} {phrase}".strip()
    guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
    notes = str(guidance.get("notes", "") or "").strip()
    if "run-key" not in notes.lower() or hive.lower() not in notes.lower():
        guidance = dict(guidance)
        guidance["notes"] = (
            f"{notes} Remove or tightly govern {hive} Run-key persistence; do not persist "
            "caller-controlled executable paths to startup locations."
        ).strip()
        item["fix_guidance"] = guidance
    return item


def _canonicalized_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return _enrich_aggregate_run_key_output(_scrub_internal_fix_synthesis_leak(finding))


def _attach_covered_signal_text(selected: list[dict[str, Any]], risk_sentinels: list[Any]) -> None:
    text_by_key = {
        _key_id(v16._sentinel_key(sentinel)): str(getattr(sentinel, "text", "") or "")
        for sentinel in risk_sentinels
    }
    text_by_site = {
        (str(getattr(sentinel, "path", "") or ""), _line_number(getattr(sentinel, "line", 0))):
        str(getattr(sentinel, "text", "") or "")
        for sentinel in risk_sentinels
    }
    for finding in selected:
        covered_text: dict[str, str] = {}
        for key in _covered_keys(finding):
            text = text_by_key.get(_key_id(key), "") or text_by_site.get((key[0], key[1]), "")
            if text:
                covered_text[_key_id(key)] = text
        if covered_text:
            finding["_dcoir_v18_covered_signal_text"] = covered_text


def _patch_v16_selector() -> None:
    original = _preserve(v16, "_select_once")

    def select_once(
        hardened: Any,
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        selected, metadata = original(hardened, findings, risk_sentinels, config)
        _attach_covered_signal_text(selected, risk_sentinels)
        return selected, metadata

    v16._select_once = select_once


def _patch_v16_rendering() -> None:
    original = _preserve(v16, "_render_comment")

    def render_comment(finding: dict[str, Any]) -> str:
        return original(_canonicalized_finding(finding))

    v16._render_comment = render_comment


def _line_present_at_anchor(file_text: str, line: int, line_text: str) -> bool:
    target = str(line_text or "")
    if not target or line <= 0:
        return False
    lines = file_text.splitlines()
    return line <= len(lines) and lines[line - 1] == target


def _patch_module_synthesis(module: Any) -> None:
    original = getattr(module, "_dcoir_required_v18_original_synthesize_fix_for_finding", None)
    if original is None:
        original = getattr(module, "synthesize_fix_for_finding", None)
        if callable(original):
            module._dcoir_required_v18_original_synthesize_fix_for_finding = original
    if not callable(original):
        return

    file_line_text = getattr(module, "file_line_text", None)
    safe_artifact_name = getattr(module, "safe_artifact_name", None)
    hardened = getattr(module, "hardened", None)

    def synthesize_fix_for_finding(
        index: int,
        finding: dict[str, Any],
        file_text: str,
        schema: dict[str, Any],
        config: Any,
    ) -> dict[str, Any]:
        enriched = original(index, finding, file_text, schema, config)
        path = str(enriched.get("path") or finding.get("path") or "")
        line = _line_number(enriched.get("line") or finding.get("line"))
        claimed_line_text = _line_text_from_finding(finding) or _line_text_from_finding(enriched)
        actual_line_text = ""
        if callable(file_line_text):
            actual_line_text = file_line_text(file_text, line)
        if not actual_line_text:
            lines = file_text.splitlines()
            if 0 < line <= len(lines):
                actual_line_text = lines[line - 1]
        guidance = enriched.get("fix_guidance") if isinstance(enriched.get("fix_guidance"), dict) else {}
        if (
            claimed_line_text
            and actual_line_text == claimed_line_text
            and _line_present_at_anchor(file_text, line, claimed_line_text)
            and _finding_has_internal_leak(enriched)
        ):
            enriched = dict(enriched)
            raw_fix_guidance = dict(guidance)
            raw_posted_fields = _raw_posted_fields(enriched)
            enriched["_anchored_line_text"] = claimed_line_text
            enriched["_dcoir_v18_internal_fix_synthesis_suppressed"] = True
            _path, _line, kind = v16._postable_key(enriched)
            if kind == v16.PYTHON_DYNAMIC_EXEC:
                enriched["fix_guidance"] = _clean_dynamic_exec_guidance(enriched, claimed_line_text)
            else:
                enriched["fix_guidance"] = _guidance_with_notes(enriched, GENERIC_INTERNAL_SYNTHESIS_NOTES)
            enriched["suggested_replacement"] = ""
            artifact_id = (
                safe_artifact_name(f"{path}-{line}", f"fix-{index:02d}")
                if callable(safe_artifact_name)
                else f"fix-{index:02d}"
            )
            writer = getattr(hardened, "write_debug_json_artifact_safely", None) if hardened is not None else None
            if callable(writer):
                writer(
                    config,
                    f"responses/fix-synthesis-v18/{index:02d}-{artifact_id}.json",
                    {
                        "path": path,
                        "line": line,
                        "suppressed_internal_fix_synthesis_leak": True,
                        "anchor_match": "exact_line",
                        "raw_fix_synthesis_preserved": True,
                        "raw_fix_guidance": raw_fix_guidance,
                        "raw_posted_fields": raw_posted_fields,
                        "normalized_fix_guidance": enriched["fix_guidance"],
                    },
                )
        return _canonicalized_finding(enriched)

    module.synthesize_fix_for_finding = synthesize_fix_for_finding


def apply_pareto_context_module(module: Any) -> None:
    _patch_v16_selector()
    _patch_v16_rendering()
    _patch_module_synthesis(module)
