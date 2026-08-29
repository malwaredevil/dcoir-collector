"""DCOIR Review v23 normalized-finding selection compatibility overlay.

The required-coverage selector was designed around sentinel-backed findings.
An ordinary model finding can already pass confidence/actionability checks and
be exactly anchored to the changed diff, yet still be erased by legacy
required-coverage selection before the v21 evidence verifier sees it.

v23 wraps the final hardened selection callables used by production. Required
and optional sentinel coverage keeps priority. Any already-normalized model
candidate dropped by that selector is restored only into spare inline capacity
and never onto a line already occupied by selected sentinel coverage. v21
remains the publication gate for every restored ordinary candidate.
"""

from __future__ import annotations

from typing import Any


VERSION = "v23"


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _path_line(finding: Any) -> tuple[str, int] | None:
    if not isinstance(finding, dict):
        return None
    path = str(finding.get("path", "") or "").strip()
    line = _line_number(finding.get("line", 0))
    return (path, line) if path and line > 0 else None


def _confidence(finding: dict[str, Any]) -> float:
    try:
        return float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _eligible_normalized_candidate(finding: Any, config: Any, hardened: Any) -> bool:
    if not isinstance(finding, dict) or _path_line(finding) is None:
        return False
    if _confidence(finding) < float(getattr(config, "minimum_confidence", 0.70)):
        return False
    checker = getattr(hardened, "non_actionable_finding_reason", None)
    if callable(checker):
        try:
            if checker(finding):
                return False
        except Exception:
            return False
    return True


def _severity_confidence_key(finding: dict[str, Any]) -> tuple[int, float, str, int, str]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    path, line = _path_line(finding) or ("", 0)
    title = str(finding.get("title", "") or "")
    return severity_rank.get(str(finding.get("severity", "low") or "low").lower(), 9), -_confidence(finding), path, line, title


def _identity(finding: dict[str, Any]) -> tuple[str, int, str, str]:
    path, line = _path_line(finding) or ("", 0)
    return path, line, str(finding.get("title", "") or "").strip(), str(finding.get("body", "") or "").strip()


def _restore_dropped_normalized(
    selected: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    config: Any,
    hardened: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    result = [dict(item) if isinstance(item, dict) else item for item in selected]
    eligible = [item for item in incoming if _eligible_normalized_candidate(item, config, hardened)]
    if len(result) >= limit or not eligible:
        return result, len(eligible), 0

    selected_sites = {_path_line(item) for item in result if isinstance(item, dict) and _path_line(item) is not None}
    selected_ids = {_identity(item) for item in result if isinstance(item, dict) and _path_line(item) is not None}
    restored = 0
    for item in sorted(eligible, key=_severity_confidence_key):
        if len(result) >= limit:
            break
        identity = _identity(item)
        site = _path_line(item)
        if identity in selected_ids:
            continue
        # Sentinel/required selection has precedence at an occupied line. This
        # also avoids duplicate ordinary comments at the same changed line.
        if site in selected_sites:
            continue
        result.append(dict(item))
        selected_ids.add(identity)
        selected_sites.add(site)
        restored += 1
    return result, len(eligible), restored


def _patch_final_hardened_selection(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    add_storage = "_dcoir_required_v23_original_add_risk_sentinel_fallback_findings"
    original_add = getattr(hardened, add_storage, None)
    if original_add is None:
        original_add = getattr(hardened, "add_risk_sentinel_fallback_findings", None)
        if callable(original_add):
            setattr(hardened, add_storage, original_add)

    if callable(original_add):
        def add_risk_sentinel_fallback_findings(
            findings: list[dict[str, Any]],
            risk_sentinels: list[Any],
            config: Any,
            unanchored_findings: list[dict[str, Any]] | None = None,
        ) -> list[dict[str, Any]]:
            incoming = [dict(item) for item in findings if isinstance(item, dict)]
            selected = original_add(findings, risk_sentinels, config, unanchored_findings)
            restored, _available, _count = _restore_dropped_normalized(selected, incoming, config, hardened)
            return restored

        hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings

    enforce_storage = "_dcoir_required_v23_original_enforce_risk_sentinel_findings"
    original_enforce = getattr(hardened, enforce_storage, None)
    if original_enforce is None:
        original_enforce = getattr(hardened, "enforce_risk_sentinel_findings", None)
        if callable(original_enforce):
            setattr(hardened, enforce_storage, original_enforce)

    if callable(original_enforce):
        def enforce_risk_sentinel_findings(
            findings: list[dict[str, Any]],
            risk_sentinels: list[Any],
            config: Any,
            unanchored_findings: list[dict[str, Any]] | None = None,
        ) -> None:
            incoming = [dict(item) for item in findings if isinstance(item, dict)]
            original_enforce(findings, risk_sentinels, config, unanchored_findings)
            restored, _available, _count = _restore_dropped_normalized(findings, incoming, config, hardened)
            findings[:] = restored

        hardened.enforce_risk_sentinel_findings = enforce_risk_sentinel_findings


def apply_pareto_context_module(module: Any) -> None:
    _patch_final_hardened_selection(module)
