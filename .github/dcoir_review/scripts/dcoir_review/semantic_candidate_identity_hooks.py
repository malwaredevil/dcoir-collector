"""Final-selection and verifier hooks for stable semantic candidate identity."""

from __future__ import annotations

from typing import Any

from dcoir_review import finding_verifier as v21
import dcoir_review_required_runtime_patch_v16 as v16


identity: Any = None
_SELECTION_STORAGE = (
    "_dcoir_review_semantic_candidate_identity_original_add_risk_sentinel_fallback_findings"
)
_VERIFIER_STORAGE = (
    "_dcoir_review_semantic_candidate_identity_original_verify_findings_for_publication"
)


def _sentinel_coverage(risk_sentinels: list[Any]) -> set[tuple[str, int, str]]:
    coverage: set[tuple[str, int, str]] = set()
    for sentinel in risk_sentinels:
        try:
            key = v16._coverage_key(v16._sentinel_key(sentinel))
        except Exception:
            continue
        if key[0] and key[2]:
            coverage.add(key)
    return coverage


def _is_required_selection(
    finding: dict[str, Any],
    required_coverage: set[tuple[str, int, str]],
) -> bool:
    if not required_coverage:
        return False
    raw = identity._raw_key(finding.get("_risk_sentinel_key"))
    if raw is not None:
        try:
            raw_coverage = v16._coverage_key(raw)
        except Exception:
            raw_coverage = None
        if raw_coverage in required_coverage:
            return True
    try:
        return v16._coverage_key(v16._postable_key(finding)) in required_coverage
    except Exception:
        return False


def _patch_required_selection(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return
    original = getattr(hardened, _SELECTION_STORAGE, None)
    if original is None:
        original = getattr(hardened, "add_risk_sentinel_fallback_findings", None)
        if callable(original):
            setattr(hardened, _SELECTION_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR semantic-candidate identity hooks could not locate the final required-sentinel selector")

    def add_risk_sentinel_fallback_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        selected = list(original(findings, risk_sentinels, config, unanchored_findings))
        if not bool(getattr(config, "semantic_candidate_identity_review", False)):
            return selected

        limit = max(0, int(getattr(config, "max_inline_comments", 12) or 12))
        protected = [
            dict(item)
            for item in findings
            if isinstance(item, dict) and identity._raw_key(item.get(identity.SEMANTIC_KEY_FIELD)) is not None
        ]
        selected_ids = {
            str(item.get(identity.CANDIDATE_ID_FIELD, "") or "")
            for item in selected
            if isinstance(item, dict) and str(item.get(identity.CANDIDATE_ID_FIELD, "") or "")
        }
        required_coverage = _sentinel_coverage(risk_sentinels)
        dispositions: list[dict[str, Any]] = []

        for source in protected:
            candidate_id = str(source.get(identity.CANDIDATE_ID_FIELD, "") or "")
            if candidate_id in selected_ids:
                dispositions.append(
                    {"candidate_id": candidate_id, "disposition": "retained-by-final-selector"}
                )
                continue

            disposition = "omitted-inline-budget"
            if len(selected) < limit:
                selected.append(dict(source))
                selected_ids.add(candidate_id)
                disposition = "reinserted-after-selector-collision"
            else:
                victim_index = None
                for index in range(len(selected) - 1, -1, -1):
                    item = selected[index]
                    if not isinstance(item, dict):
                        continue
                    item_id = str(item.get(identity.CANDIDATE_ID_FIELD, "") or "")
                    if item_id or _is_required_selection(item, required_coverage):
                        continue
                    victim_index = index
                    break
                if victim_index is not None:
                    selected[victim_index] = dict(source)
                    selected_ids.add(candidate_id)
                    disposition = "reinserted-by-displacing-nonrequired-fallback"
            dispositions.append(
                {"candidate_id": candidate_id, "disposition": disposition}
            )

        selected = selected[:limit]
        writer = getattr(hardened, "write_debug_json_artifact_safely", None)
        if callable(writer):
            writer(
                config,
                identity.FINAL_SELECTION_ARTIFACT_PATH,
                {
                    "schema_version": "dcoir_review_v51_final_selection_integrity_v1",
                    "version": identity.VERSION,
                    "inline_limit": limit,
                    "required_sentinel_count": len(required_coverage),
                    "protected_semantic_candidate_count": len(protected),
                    "dispositions": dispositions,
                    "selected": [identity._snapshot_candidate(item) for item in selected if isinstance(item, dict)],
                },
            )
        return selected

    def enforce_risk_sentinel_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> None:
        findings[:] = add_risk_sentinel_fallback_findings(
            findings, risk_sentinels, config, unanchored_findings
        )

    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings
    hardened.enforce_risk_sentinel_findings = enforce_risk_sentinel_findings


def _patch_verifier_debug(module: Any) -> None:
    original = getattr(v21, _VERIFIER_STORAGE, None)
    if original is None:
        original = getattr(v21, "verify_findings_for_publication", None)
        if callable(original):
            setattr(v21, _VERIFIER_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR semantic-candidate identity hooks could not locate the publication verifier")

    def verify_findings_for_publication(
        review_module: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        if bool(getattr(config, "semantic_candidate_identity_review", False)):
            writer = getattr(review_module.hardened, "write_debug_json_artifact_safely", None)
            if callable(writer):
                writer(
                    config,
                    identity.VERIFIER_ARTIFACT_PATH,
                    {
                        "schema_version": "dcoir_review_v51_verifier_candidate_provenance_v1",
                        "head_sha": str(pr.get("head", {}).get("sha", "") or "").strip(),
                        "candidate_count": len(findings),
                        "candidates": [identity._snapshot_candidate(item) for item in findings if isinstance(item, dict)],
                    },
                )
        return original(review_module, findings, gh, pr, config, reporter)

    v21.verify_findings_for_publication = verify_findings_for_publication


def apply_pareto_context_module(module: Any, identity_module: Any) -> None:
    global identity
    identity = identity_module
    _patch_required_selection(module)
    _patch_verifier_debug(module)
