"""Explicit normalized-finding selection stage for DCOIR Review.

Required/optional sentinel selection remains authoritative. This owner preserves
eligible ordinary normalized findings that a sentinel-oriented selector drops,
but does so as a pure stage invoked by the review pipeline rather than by
storing and replacing selector callables at runtime.
"""

from __future__ import annotations

from typing import Any


APPLIED_MARKER = "_dcoir_normalized_finding_selection_applied"


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
    return (
        severity_rank.get(str(finding.get("severity", "low") or "low").lower(), 9),
        -_confidence(finding),
        path,
        line,
        title,
    )


def _identity(finding: dict[str, Any]) -> tuple[str, int, str, str]:
    path, line = _path_line(finding) or ("", 0)
    return (
        path,
        line,
        str(finding.get("title", "") or "").strip(),
        str(finding.get("body", "") or "").strip(),
    )


def restore_dropped_normalized(
    selected: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    config: Any,
    hardened: Any,
) -> list[dict[str, Any]]:
    """Restore eligible ordinary candidates after one explicit selection pass."""

    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    result = [dict(item) if isinstance(item, dict) else item for item in selected]
    eligible = [item for item in incoming if _eligible_normalized_candidate(item, config, hardened)]
    if len(result) >= limit or not eligible:
        return result

    selected_sites = {
        _path_line(item)
        for item in result
        if isinstance(item, dict) and _path_line(item) is not None
    }
    selected_ids = {
        _identity(item)
        for item in result
        if isinstance(item, dict) and _path_line(item) is not None
    }
    for item in sorted(eligible, key=_severity_confidence_key):
        if len(result) >= limit:
            break
        identity = _identity(item)
        site = _path_line(item)
        if identity in selected_ids or site in selected_sites:
            continue
        result.append(dict(item))
        selected_ids.add(identity)
        selected_sites.add(site)
    return result


def apply_pareto_context_module(module: Any) -> None:
    """Compatibility registration only; production composition is explicit."""

    setattr(module, APPLIED_MARKER, True)
