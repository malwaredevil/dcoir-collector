"""Seventeenth DCOIR Review calibration overlay.

v17 is intentionally narrow. It runs after v16 and does not replace the v16
hard-required selector. It only tightens #343 calibration defects:

- keep hard-required coverage accounting separate from optional pressure;
- use spare inline capacity for optional pressure only after required coverage
  is complete;
- render env-token, Run-key, and Python dynamic-exec findings with anchored
  semantics; and
- suppress impossible fix-synthesis "missing context" guidance when the
  anchored line was already present in the fetched head-file context.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_strict_runtime_patches as strict


VERSION = "v17"

FALSE_MISSING_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"does\s+not\s+contain|"
    r"missing\s+from\s+(?:the\s+)?(?:head-)?file\s+context|"
    r"(?:function|body|line)\s+is\s+missing|"
    r"provide\s+the\s+complete\s+file\s+content|"
    r"without\s+the\s+exact\s+code\s+present"
    r")\b",
    re.IGNORECASE,
)

ENV_TOKEN_TITLE = "Environment token forwarded to request-controlled callback"
ENV_TOKEN_BODY = (
    "This line forwards an environment token in an authorization-bearing request to a "
    "request-controlled callback or URL. Treat this as token forwarding and SSRF risk, "
    "not as an embedded credential unless the source contains a literal token value."
)
ENV_TOKEN_NOTES = (
    "Keep the token on the trusted side of the boundary and allowlist callback destinations "
    "before any authorization header is added."
)
DYNAMIC_EXEC_NOTES = (
    "The anchored line is present in the head-file context. Remove the dynamic execution "
    "or replace it with a non-executing parser, constrained AST allowlist, or explicit "
    "allowlist. Do not replace eval or exec with another dynamic execution primitive."
)


def _line_has_env_token(line_text: str) -> bool:
    lower = str(line_text or "").lower()
    return any(
        token in lower
        for token in (
            "os.environ",
            "os.getenv",
            "$env:",
            "environment]::getenvironmentvariable",
            "dcoir_token",
        )
    )


def _preserve(module: Any, name: str) -> Any:
    storage = f"_dcoir_required_v17_original_{name.lstrip('_')}"
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


def _line_text_from_finding(finding: dict[str, Any]) -> str:
    return str(
        finding.get("_anchored_line_text")
        or finding.get("text")
        or finding.get("line_text")
        or ""
    )


def _run_key_hive(line_text: str) -> str:
    lower = str(line_text or "").lower()
    if "hkcu:" in lower or "hkey_current_user" in lower:
        return "HKCU"
    if "hklm:" in lower or "hkey_local_machine" in lower:
        return "HKLM"
    return "Windows"


def _guidance_with_notes(finding: dict[str, Any], notes: str) -> dict[str, str]:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    language = str(guidance.get("language") or _language_hint(str(finding.get("path", "") or "")))
    return {"language": language, "notes": notes}


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


def _false_missing_context(value: Any) -> bool:
    return bool(FALSE_MISSING_CONTEXT_RE.search(str(value or "")))


def _canonicalized_finding(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    path, line, kind = v16._postable_key(item)
    line_text = _line_text_from_finding(item)
    item.setdefault("_risk_sentinel_key", [path, line, kind])
    if line_text:
        item["_anchored_line_text"] = line_text

    if kind in {v5.PYTHON_ENV_TOKEN, v5.PS_ENV_TOKEN} and _line_has_env_token(line_text):
        item["title"] = ENV_TOKEN_TITLE
        item["body"] = ENV_TOKEN_BODY
        item["suggested_replacement"] = ""
        item["fix_guidance"] = _guidance_with_notes(item, ENV_TOKEN_NOTES)
        return item

    if kind == v13.PS_RUN_KEY_PERSISTENCE:
        hive = _run_key_hive(line_text)
        if hive in {"HKCU", "HKLM"}:
            item["title"] = f"PowerShell writes {hive} Run-key persistence"
            item["body"] = (
                f"This line writes a Run-key persistence value under {hive}. "
                "Caller-controlled executable values must not be persisted to startup locations."
            )
        else:
            item["title"] = "PowerShell writes a Windows Run-key persistence location"
            item["body"] = (
                "This line writes a Windows Run-key persistence value. Caller-controlled "
                "executable values must not be persisted to startup locations."
            )
        return item

    if kind == v16.PYTHON_DYNAMIC_EXEC:
        title, body, _notes = v16._template_for_kind(kind)
        item["title"] = title
        item["body"] = body
        guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
        if item.get("_dcoir_v17_false_missing_context_suppressed") and _false_missing_context(guidance.get("notes", "")):
            item["fix_guidance"] = _guidance_with_notes(item, DYNAMIC_EXEC_NOTES)
            item["suggested_replacement"] = ""
    return item


def _record_for_sentinel(
    sentinel: Any,
    reason: str,
    required: set[v16.SentinelKey],
    selected_cov: set[v16.SentinelKey],
    selected_count: int,
    limit: int,
) -> dict[str, Any]:
    record = v16._sentinel_record(sentinel, reason, required, selected_cov, limit)
    record["selected_count"] = selected_count
    record["selected_postable_count"] = selected_count
    record["covered_sentinel_count"] = len(selected_cov)
    return record


def _optional_pressure_sentinels(risk_sentinels: list[Any]) -> list[Any]:
    kept: dict[v16.SentinelKey, Any] = {}
    for sentinel in risk_sentinels:
        key = v16._sentinel_key(sentinel)
        if key[2] not in v16.OPTIONAL_PRESSURE_KINDS:
            continue
        coverage = v16._coverage_key(key)
        current = kept.get(coverage)
        if current is None:
            kept[coverage] = sentinel
            continue
        current_key = v16._sentinel_key(current)
        if (v16._kind_rank(key[2]), key[1]) < (v16._kind_rank(current_key[2]), current_key[1]):
            kept[coverage] = sentinel
    return sorted(
        kept.values(),
        key=lambda item: (
            v16._kind_rank(v16._sentinel_key(item)[2]),
            v16._sentinel_key(item)[0],
            v16._sentinel_key(item)[1],
        ),
    )


def _refresh_metadata(
    metadata: dict[str, Any],
    selected: list[dict[str, Any]],
    risk_sentinels: list[Any],
    limit: int,
) -> dict[str, Any]:
    core_targets = v16._core_sentinels(risk_sentinels)
    required_cov = {v16._coverage_key(v16._sentinel_key(sentinel)) for sentinel in core_targets}
    selected_cov: set[v16.SentinelKey] = set()
    for finding in selected:
        selected_cov.update(v16._coverage_from_finding(finding))
    selected_keys = [v16._postable_key(item) for item in selected]

    aggregate_covered = []
    omitted_required = []
    for sentinel in core_targets:
        key = v16._sentinel_key(sentinel)
        coverage = v16._coverage_key(key)
        if coverage in selected_cov:
            if not any(v16._postable_key(item) == key for item in selected):
                aggregate_covered.append(
                    _record_for_sentinel(sentinel, "aggregate_covered", required_cov, selected_cov, len(selected), limit)
                )
        else:
            omitted_required.append(
                _record_for_sentinel(sentinel, "omitted_due_to_inline_budget", required_cov, selected_cov, len(selected), limit)
            )

    optional_overflow = []
    for sentinel in risk_sentinels:
        key = v16._sentinel_key(sentinel)
        coverage = v16._coverage_key(key)
        if coverage in selected_cov or coverage in required_cov:
            continue
        if key[2] in v16.OPTIONAL_PRESSURE_KINDS:
            reason = "omitted_due_to_inline_budget" if len(selected) >= limit else "omitted_after_required_coverage_accounting"
            optional_overflow.append(
                _record_for_sentinel(sentinel, reason, required_cov, selected_cov, len(selected), limit)
            )

    refreshed = dict(metadata)
    refreshed.update(
        {
            "version": VERSION,
            "base_version": getattr(v16, "VERSION", "v16"),
            "inline_limit": limit,
            "final_postable_count": len(selected),
            "unused_inline_slots": max(0, limit - len(selected)),
            "hard_required_count": len(required_cov),
            "covered_required_count": len(required_cov & selected_cov),
            "selected_keys": [v16._key_text(key) for key in selected_keys],
            "posted_required_sentinels": [v16._key_text(key) for key in selected_keys if v16._coverage_key(key) in required_cov],
            "aggregate_covered_sentinels": aggregate_covered[:100],
            "omitted_required_sentinels": omitted_required[:100],
            "omitted_optional_high_risk_sentinels": optional_overflow[:100],
            "overflow_required_count": len(omitted_required),
            "overflow_optional_high_risk_count": len(optional_overflow),
            "partial_overflow": bool(omitted_required or optional_overflow),
            "required_partial_overflow": bool(omitted_required),
            "optional_pressure_overflow": bool(optional_overflow),
            "optional_pressure_policy": (
                "Optional TypeScript pressure may be posted only after all hard-required "
                "YAML/Python/PowerShell sentinels are posted or aggregate-covered."
            ),
            "coverage_ledger_readback": {
                "required_covered": len(required_cov & selected_cov),
                "required_total": len(required_cov),
                "required_omitted": len(omitted_required),
                "inline_posted": len(selected),
                "inline_limit": limit,
                "optional_omitted": len(optional_overflow),
            },
            "required_ledger_schema": "v17_required_vs_optional_pressure",
            "core_required_families": v16._family_counts(required_cov),
            "selected_coverage_families": v16._family_counts(selected_cov),
            "kubernetes_policy": "optional_bonus_only",
        }
    )
    return refreshed


def _patch_v16_selector() -> None:
    original = _preserve(v16, "_select_once")

    def select_once(hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        selected, metadata = original(hardened, findings, risk_sentinels, config)
        limit = max(0, int(getattr(config, "max_inline_comments", 12)))
        selected_cov: set[v16.SentinelKey] = set()
        for finding in selected:
            selected_cov.update(v16._coverage_from_finding(finding))
        required_cov = {v16._coverage_key(v16._sentinel_key(sentinel)) for sentinel in v16._core_sentinels(risk_sentinels)}
        if required_cov and required_cov <= selected_cov:
            for sentinel in _optional_pressure_sentinels(risk_sentinels):
                if len(selected) >= limit:
                    break
                coverage = v16._coverage_key(v16._sentinel_key(sentinel))
                if coverage in selected_cov:
                    continue
                finding = v16._finding_for_sentinel(sentinel)
                selected.append(finding)
                selected_cov.update(v16._coverage_from_finding(finding))
        metadata = _refresh_metadata(metadata, selected, risk_sentinels, limit)
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
    if line <= len(lines) and lines[line - 1] == target:
        return True
    return False


def _patch_strict_runtime() -> None:
    original_prompt = _preserve(strict, "_build_strict_fix_synthesis_prompt")

    def build_strict_fix_synthesis_prompt(
        base: Any,
        finding: dict[str, Any],
        path: str,
        line: int,
        line_text: str,
        file_text: str,
        config: Any,
    ) -> str:
        prompt = original_prompt(base, finding, path, line, line_text, file_text, config)
        invariant = (
            "\n- The Current anchored line text is copied from the fetched head-file context. "
            "If that exact anchored line appears in the full context below, do not say the "
            "line, function, or file context is missing; leave code fields empty and put "
            "conceptual repair guidance in notes when no exact code replacement is safe."
        )
        anchor = "\n- Do not recommend eval, exec, or dynamic execution."
        if anchor in prompt and "do not say the line, function, or file context is missing" not in prompt:
            prompt = prompt.replace(anchor, f"{anchor}{invariant}")
        return prompt

    strict._build_strict_fix_synthesis_prompt = build_strict_fix_synthesis_prompt
