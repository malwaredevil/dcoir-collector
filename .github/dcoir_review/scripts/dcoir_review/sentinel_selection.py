"""Stable ordinary-finding / deterministic-sentinel selection ownership.

The normalized model finding has already passed confidence/actionability checks
and is anchored to an added changed line. Required-sentinel selection may add or
prioritize deterministic findings for real risk sentinels, but it must never
relocate or semantically rewrite an ordinary normalized model finding merely
because legacy classifiers infer a sentinel kind from its prose.

This owner preserves normalized model findings verbatim and merges only
selection outputs that provably correspond to a risk sentinel actually detected
in the changed diff. With no real risk sentinels, selection is a no-op.
"""

from __future__ import annotations

from typing import Any

import dcoir_review.risk_sentinel_identity as v3
import dcoir_review.risk_sentinel_primitives as v16
import dcoir_review.truthy_literal_policy as v20

from dcoir_review import environment_token_detection



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



SELECTION_POLICY_VERSION = "required-vs-optional-pressure-v1"


def _patch_risk_sentinel_priority(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return
    original = environment_token_detection.select_required_first

    def select_risk_sentinels(sentinels: list[Any], max_anchors: int | None = None) -> list[Any]:
        deduped = v3._dedupe_sentinels(list(sentinels))
        if max_anchors is None or len(deduped) <= max_anchors:
            return deduped
        limit = max(0, int(max_anchors))
        selected: list[Any] = []
        seen: set[tuple[str, int, str]] = set()

        def add(sentinel: Any) -> None:
            key = v3._sentinel_key(sentinel)
            if key not in seen and len(selected) < limit:
                seen.add(key)
                selected.append(sentinel)

        for kind in v3.HARD_REQUIRED_KIND_ORDER:
            for sentinel in deduped:
                if v3._sentinel_kind(sentinel) == kind:
                    add(sentinel)
                    break
        remaining = [item for item in deduped if v3._sentinel_key(item) not in seen]
        budget = max(0, limit - len(selected))
        if budget and remaining:
            try:
                remaining = list(original(remaining, budget))
            except TypeError:
                remaining = list(original(remaining))
            for sentinel in remaining:
                add(sentinel)
        return selected[:limit]

    hardened.select_risk_sentinels = select_risk_sentinels




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


def _append_optional_pressure(
    selected: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
) -> list[dict[str, Any]]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12) or 12))
    selected_cov: set[v16.SentinelKey] = set()
    for finding in selected:
        selected_cov.update(v16._coverage_from_finding(finding))
    required_cov = {
        v16._coverage_key(v16._sentinel_key(sentinel))
        for sentinel in v16._core_sentinels(risk_sentinels)
    }
    if not required_cov or not required_cov <= selected_cov:
        return selected
    for sentinel in _optional_pressure_sentinels(risk_sentinels):
        if len(selected) >= limit:
            break
        coverage = v16._coverage_key(v16._sentinel_key(sentinel))
        if coverage in selected_cov:
            continue
        finding = v16._finding_for_sentinel(sentinel)
        selected.append(finding)
        selected_cov.update(v16._coverage_from_finding(finding))
    return selected


def _refresh_selection_metadata(
    selected: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
) -> None:
    core = getattr(v16, "core", None)
    summary = getattr(core, "SELECTION_SUMMARY", None)
    if not isinstance(summary, dict):
        return

    limit = max(0, int(getattr(config, "max_inline_comments", 12) or 12))
    core_targets = v16._core_sentinels(risk_sentinels)
    required_cov = {v16._coverage_key(v16._sentinel_key(sentinel)) for sentinel in core_targets}
    selected_cov: set[v16.SentinelKey] = set()
    for finding in selected:
        selected_cov.update(v16._coverage_from_finding(finding))
    selected_keys = [v16._postable_key(item) for item in selected]

    aggregate_covered: list[dict[str, Any]] = []
    omitted_required: list[dict[str, Any]] = []
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

    optional_overflow: list[dict[str, Any]] = []
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

    refreshed = dict(summary)
    refreshed.update(
        {
            "version": SELECTION_POLICY_VERSION,
            "base_version": getattr(v16, "VERSION", "v16"),
            "inline_limit": limit,
            "final_postable_count": len(selected),
            "unused_inline_slots": max(0, limit - len(selected)),
            "hard_required_count": len(required_cov),
            "covered_required_count": len(required_cov & selected_cov),
            "selected_keys": [v16._key_text(key) for key in selected_keys],
            "posted_required_sentinels": [
                v16._key_text(key) for key in selected_keys if v16._coverage_key(key) in required_cov
            ],
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
            "required_ledger_schema": "stable_required_vs_optional_pressure_v1",
            "core_required_families": v16._family_counts(required_cov),
            "selected_coverage_families": v16._family_counts(selected_cov),
            "kubernetes_policy": "optional_bonus_only",
        }
    )
    summary.clear()
    summary.update(refreshed)

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

        selected = _append_optional_pressure(
            list(original(findings, risk_sentinels, config, unanchored_findings)),
            risk_sentinels,
            config,
        )
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
                final = required[:limit]
                _refresh_selection_metadata(final, risk_sentinels, config)
                return final

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
        _refresh_selection_metadata(merged, risk_sentinels, config)
        return merged

    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings


def apply_pareto_context_module(module: Any) -> None:
    # v20 is now a helper-definition layer beneath stable selection and stable truthy-literal precision.
    # Preserve its truthy-literal registry handoff here without retaining a
    # standalone historical runtime root.
    v20._patch_v16_selection_registry()
    _patch_risk_sentinel_priority(module)
    _patch_final_sentinel_selection(module)
