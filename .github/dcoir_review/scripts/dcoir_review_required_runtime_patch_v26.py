"""DCOIR Review v26 immutable ordinary-finding anchor overlay.

The normalized model finding has already passed confidence/actionability checks
and is anchored to an added changed line. Required-sentinel selection may add or
prioritize deterministic findings for real risk sentinels, but it must never
relocate or semantically rewrite an ordinary normalized model finding merely
because legacy classifiers infer a sentinel kind from its prose.

v26 therefore preserves normalized model findings verbatim and merges only
selection outputs that provably correspond to a risk sentinel actually detected
in the changed diff. With no real risk sentinels, selection is a no-op.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16


VERSION = "v26"


def _line(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _site(item: dict[str, Any]) -> tuple[str, int]:
    return str(item.get("path", "") or "").strip(), _line(item.get("line", 0))


def _raw_key(value: Any) -> tuple[str, int, str] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    path = str(value[0] or "").strip()
    line = _line(value[1])
    kind = str(value[2] or "").strip()
    return (path, line, kind) if path and line > 0 and kind else None


def _real_sentinel_keys(risk_sentinels: list[Any]) -> set[tuple[str, int, str]]:
    keys: set[tuple[str, int, str]] = set()
    for sentinel in risk_sentinels:
        try:
            path, line, kind = v16._sentinel_key(sentinel)
        except Exception:
            continue
        path = str(path or "").strip()
        line = _line(line)
        kind = str(kind or "").strip()
        if path and line > 0 and kind:
            keys.add((path, line, kind))
    return keys


def _finding_has_real_sentinel_provenance(
    finding: dict[str, Any],
    real_keys: set[tuple[str, int, str]],
) -> bool:
    if not real_keys:
        return False
    key = _raw_key(finding.get("_risk_sentinel_key"))
    if key in real_keys:
        return True
    covered = finding.get("covered_risk_sentinel_keys")
    if isinstance(covered, list) and any(_raw_key(raw) in real_keys for raw in covered):
        return True
    try:
        postable = v16._postable_key(finding)
        normalized = (str(postable[0] or "").strip(), _line(postable[1]), str(postable[2] or "").strip())
    except Exception:
        return False
    return normalized in real_keys


def _patch_final_sentinel_selection(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return
    storage = "_dcoir_required_v26_original_add_risk_sentinel_fallback_findings"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "add_risk_sentinel_fallback_findings", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        return

    def add_risk_sentinel_fallback_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        originals = [dict(item) for item in findings if isinstance(item, dict)]
        limit = max(0, int(getattr(config, "max_inline_comments", 12) or 12))
        if limit <= 0:
            return []

        # No deterministic risk signal exists, so there is nothing for the
        # sentinel selector to add, rewrite, or reprioritize. Preserve the
        # normalized model anchors and semantics exactly.
        if not risk_sentinels:
            return originals[:limit]

        selected = original(findings, risk_sentinels, config, unanchored_findings)
        real_keys = _real_sentinel_keys(risk_sentinels)
        required: list[dict[str, Any]] = []
        occupied_sites: set[tuple[str, int]] = set()
        seen_required: set[tuple[str, int, str]] = set()

        for item in selected:
            if not isinstance(item, dict) or not _finding_has_real_sentinel_provenance(item, real_keys):
                continue
            raw = _raw_key(item.get("_risk_sentinel_key"))
            if raw is None:
                try:
                    key = v16._postable_key(item)
                    raw = (str(key[0] or "").strip(), _line(key[1]), str(key[2] or "").strip())
                except Exception:
                    raw = None
            if raw is None or raw in seen_required:
                continue
            required.append(dict(item))
            seen_required.add(raw)
            occupied_sites.add(_site(item))
            if len(required) >= limit:
                return required[:limit]

        merged = list(required)
        seen_model: set[tuple[str, int, str, str]] = set()
        for item in originals:
            if len(merged) >= limit:
                break
            path, line = _site(item)
            if not path or line <= 0 or (path, line) in occupied_sites:
                continue
            identity = (
                path,
                line,
                str(item.get("title", "") or ""),
                str(item.get("body", "") or ""),
            )
            if identity in seen_model:
                continue
            merged.append(dict(item))
            seen_model.add(identity)
        return merged

    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings


def apply_pareto_context_module(module: Any) -> None:
    _patch_final_sentinel_selection(module)
