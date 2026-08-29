"""DCOIR Review v23 ordinary-finding selection compatibility overlay.

The required-coverage selector was designed around sentinel-backed findings.
An ordinary model finding can already be confidence-filtered and exactly
anchored to the changed diff yet still have no risk-sentinel kind. v16 drops
such findings because its selection coverage key requires a non-empty kind.

v23 preserves those already-normalized ordinary findings in spare inline
capacity after hard-required selection. It never invents a sentinel kind,
never displaces required coverage, and leaves the v21 evidence verifier as the
publication gate for every retained ordinary finding.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16


VERSION = "v23"


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _severity_confidence_key(finding: dict[str, Any]) -> tuple[int, float, str, int, str]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    try:
        confidence = float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    path = str(finding.get("path", "") or "").strip()
    line = _line_number(finding.get("line", 0))
    title = str(finding.get("title", "") or "")
    return severity_rank.get(str(finding.get("severity", "low") or "low").lower(), 9), -confidence, path, line, title


def _ordinary_candidate(finding: Any) -> tuple[str, int] | None:
    if not isinstance(finding, dict):
        return None
    path, line, kind = v16._postable_key(finding)
    path = str(path or "").strip()
    line = _line_number(line)
    if not path or line <= 0 or kind:
        return None
    return path, line


def _ordinary_identity(finding: dict[str, Any]) -> tuple[str, int, str, str]:
    path, line = _ordinary_candidate(finding) or ("", 0)
    return (
        path,
        line,
        str(finding.get("title", "") or "").strip(),
        str(finding.get("body", "") or "").strip(),
    )


def _patch_final_selector() -> None:
    storage = "_dcoir_required_v23_original_select_once"
    original = getattr(v16, storage, None)
    if original is None:
        original = getattr(v16, "_select_once", None)
        if callable(original):
            setattr(v16, storage, original)
    if not callable(original):
        return

    def select_once(
        hardened: Any,
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        selected, metadata = original(hardened, findings, risk_sentinels, config)
        limit = max(0, int(getattr(config, "max_inline_comments", 12)))
        if len(selected) >= limit:
            refreshed = dict(metadata)
            refreshed["ordinary_model_candidates_retained"] = 0
            refreshed["ordinary_model_candidates_available"] = sum(
                1 for item in findings if _ordinary_candidate(item) is not None
            )
            return selected, refreshed

        selected_sites = {
            (str(item.get("path", "") or "").strip(), _line_number(item.get("line", 0)))
            for item in selected
            if isinstance(item, dict)
        }
        selected_ordinary_ids = {
            _ordinary_identity(item)
            for item in selected
            if isinstance(item, dict) and _ordinary_candidate(item) is not None
        }
        ordinary = [item for item in findings if _ordinary_candidate(item) is not None]
        retained = 0
        for item in sorted(ordinary, key=_severity_confidence_key):
            if len(selected) >= limit:
                break
            identity = _ordinary_identity(item)
            site = identity[:2]
            if identity in selected_ordinary_ids:
                continue
            # Avoid posting a second ordinary comment at a site already occupied
            # by required/optional sentinel coverage; the sentinel has precedence.
            if site in selected_sites:
                continue
            selected.append(dict(item))
            selected_ordinary_ids.add(identity)
            selected_sites.add(site)
            retained += 1

        refreshed = dict(metadata)
        refreshed.update(
            {
                "version": VERSION,
                "selection_base_version": str(metadata.get("version", "") or getattr(v16, "VERSION", "v16")),
                "final_postable_count": len(selected),
                "unused_inline_slots": max(0, limit - len(selected)),
                "ordinary_model_candidates_available": len(ordinary),
                "ordinary_model_candidates_retained": retained,
                "ordinary_model_candidate_policy": "spare-capacity-after-sentinel-selection; verifier-required-before-publication",
            }
        )
        return selected, refreshed

    v16._select_once = select_once


def apply_pareto_context_module(module: Any) -> None:
    del module
    _patch_final_selector()
