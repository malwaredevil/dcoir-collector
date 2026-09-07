"""Architecture-B v51 semantic-candidate identity preservation overlay.

The #494/#497 live acceptance showed an ordinary semantic finding could be
reclassified from free-text prose as a deterministic risk kind before verifier
input. In the observed case, a stale authorization-cache finding mentioned the
word "authorization", legacy normalization inferred ``python_ssrf``, and the
required-risk normalizer replaced the finding with an unrelated environment
token/callback template. The verifier correctly rejected that replacement, but
the original semantic candidate had already been lost.

v51 makes risk-kind provenance explicit at the ranking boundary. Candidates
without an explicit risk-sentinel key or matching anchored source-line signal
receive a stable neutral semantic identity before legacy ranking/selection.
Legacy ordering and required-sentinel coverage remain intact, but unsupported
risk-kind inference can no longer rewrite or collide away an unrelated semantic
candidate. Publication verification remains authoritative and unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v5 as v5

VERSION = "v51"
_APPLIED_ATTR = "_dcoir_v51_applied"
_CONFIG_STORAGE = "_dcoir_v51_original_load_pareto_context_config"
_RANK_STORAGE = "_dcoir_v51_original_rank_findings_for_required_budget"
_POSTABLE_STORAGE = "_dcoir_v51_original_postable_key"
_VERIFIER_STORAGE = "_dcoir_v51_original_verify_findings_for_publication"
_SELECTION_STORAGE = "_dcoir_v51_original_add_risk_sentinel_fallback_findings"

CANDIDATE_ID_FIELD = "_dcoir_v51_candidate_id"
SEMANTIC_KEY_FIELD = "_dcoir_v51_semantic_candidate_key"
SELECTION_ARTIFACT_PATH = "metadata/v51-candidate-integrity.json"
FINAL_SELECTION_ARTIFACT_PATH = "metadata/v51-final-selection-integrity.json"
VERIFIER_ARTIFACT_PATH = "metadata/v51-verifier-candidate-provenance.json"
SEMANTIC_KIND_PREFIX = "semantic_candidate:"


def _line(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _candidate_id(finding: dict[str, Any]) -> str:
    existing = str(finding.get(CANDIDATE_ID_FIELD, "") or "").strip()
    if existing:
        return existing
    payload = {
        "path": str(finding.get("path", "") or "").strip(),
        "line": _line(finding.get("line", 0)),
        "title": str(finding.get("title", "") or "").strip(),
        "body": str(finding.get("body", "") or "").strip(),
        "validation": str(finding.get("validation", "") or "").strip(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"candidate-{digest[:20]}"


def _semantic_key(finding: dict[str, Any], candidate_id: str) -> tuple[str, int, str]:
    return (
        str(finding.get("path", "") or "").strip(),
        _line(finding.get("line", 0)),
        f"{SEMANTIC_KIND_PREFIX}{candidate_id}",
    )


def _raw_key(value: Any) -> tuple[str, int, str] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    path = str(value[0] or "").strip()
    line = _line(value[1])
    kind = str(value[2] or "").strip()
    return (path, line, kind) if path and line > 0 and kind else None


def _original_postable_key() -> Any:
    original = getattr(v16, _POSTABLE_STORAGE, None)
    if callable(original):
        return original
    current = getattr(v16, "_postable_key", None)
    if not callable(current):
        raise RuntimeError("DCOIR v51 could not locate v16 postable-key helper")
    setattr(v16, _POSTABLE_STORAGE, current)
    return current


def _legacy_normalized_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    original = _original_postable_key()
    try:
        normalized = v5._normalize_comment_finding(dict(finding))
        key = original(normalized)
        return str(key[0] or "").strip(), _line(key[1]), str(key[2] or "").strip()
    except Exception:
        try:
            key = original(dict(finding))
            return str(key[0] or "").strip(), _line(key[1]), str(key[2] or "").strip()
        except Exception:
            return (
                str(finding.get("path", "") or "").strip(),
                _line(finding.get("line", 0)),
                "",
            )


def _risk_provenance(finding: dict[str, Any], inferred: tuple[str, int, str]) -> str:
    path, line, kind = inferred
    if not path or line <= 0 or not kind or kind.startswith(SEMANTIC_KIND_PREFIX):
        return ""

    explicit = _raw_key(finding.get("_risk_sentinel_key"))
    if explicit is not None:
        try:
            if v16._coverage_key(explicit) == v16._coverage_key(inferred):
                return "explicit-risk-sentinel-key"
        except Exception:
            if explicit == inferred:
                return "explicit-risk-sentinel-key"

    anchored = str(finding.get("_anchored_line_text", "") or "")
    if anchored:
        try:
            observed = str(v16._line_kind(path, anchored) or "").strip()
        except Exception:
            observed = ""
        if observed == kind:
            return "anchored-source-line"
    return ""


def _prepare_candidate(finding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    item = dict(finding)
    candidate_id = _candidate_id(item)
    item[CANDIDATE_ID_FIELD] = candidate_id
    inferred = _legacy_normalized_key(item)
    provenance = _risk_provenance(item, inferred)
    disposition = "unclassified-semantic-candidate"
    if inferred[2] and not inferred[2].startswith(SEMANTIC_KIND_PREFIX):
        if provenance:
            disposition = "risk-provenance-preserved"
        else:
            semantic_key = _semantic_key(item, candidate_id)
            item[SEMANTIC_KEY_FIELD] = list(semantic_key)
            disposition = "semantic-identity-protected"
    record = {
        "candidate_id": candidate_id,
        "path": str(item.get("path", "") or "").strip(),
        "line": _line(item.get("line", 0)),
        "source_title": str(finding.get("title", "") or "").strip(),
        "legacy_inferred_kind": inferred[2],
        "risk_provenance": provenance or "none",
        "disposition": disposition,
        "semantic_key": list(item.get(SEMANTIC_KEY_FIELD, []) or []),
    }
    return item, record


def _restore_semantic_candidate(
    selected: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    restored = dict(selected)
    # Preserve the model/adjudicator semantics that entered the ranking boundary.
    # Risk-specific repair guidance produced from unsupported inference is dropped;
    # the independent verified-repair pipeline may author safe guidance later.
    for field in (
        "title",
        "body",
        "validation",
        "severity",
        "confidence",
        "path",
        "line",
        "_anchored_line_text",
    ):
        if field in source:
            restored[field] = copy.deepcopy(source[field])
        elif field in restored and field == "_anchored_line_text":
            restored.pop(field, None)
    restored.pop("fix_guidance", None)
    restored.pop("suggested_replacement", None)
    restored[CANDIDATE_ID_FIELD] = str(source.get(CANDIDATE_ID_FIELD, "") or "")
    if source.get(SEMANTIC_KEY_FIELD):
        restored[SEMANTIC_KEY_FIELD] = copy.deepcopy(source[SEMANTIC_KEY_FIELD])
    return restored


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, _CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, _CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v51 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.semantic_candidate_identity_review = module.hardened.bool_value(
            data, "semantic_candidate_identity_review", True
        )
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _patch_postable_key() -> None:
    original = _original_postable_key()

    def postable_key(finding: dict[str, Any]):
        semantic = _raw_key(finding.get(SEMANTIC_KEY_FIELD))
        if semantic is not None and semantic[2].startswith(SEMANTIC_KIND_PREFIX):
            return semantic
        return original(finding)

    v16._postable_key = postable_key


def _snapshot_candidate(finding: dict[str, Any]) -> dict[str, Any]:
    semantic_key = _raw_key(finding.get(SEMANTIC_KEY_FIELD))
    risk_key = _raw_key(finding.get("_risk_sentinel_key"))
    return {
        "candidate_id": str(finding.get(CANDIDATE_ID_FIELD, "") or ""),
        "path": str(finding.get("path", "") or "").strip(),
        "line": _line(finding.get("line", 0)),
        "title": str(finding.get("title", "") or "").strip(),
        "semantic_key": list(semantic_key) if semantic_key is not None else [],
        "risk_sentinel_key": list(risk_key) if risk_key is not None else [],
    }


def _patch_ranker(module: Any) -> None:
    original = getattr(module, _RANK_STORAGE, None)
    if original is None:
        original = getattr(module, "rank_findings_for_required_budget", None)
        if callable(original):
            setattr(module, _RANK_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v51 could not locate rank_findings_for_required_budget")

    def rank_findings_for_required_budget(
        findings: list[dict[str, Any]], config: Any
    ) -> list[dict[str, Any]]:
        if not bool(getattr(config, "semantic_candidate_identity_review", False)):
            return original(findings, config)

        guarded: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        sources: dict[str, dict[str, Any]] = {}
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            item, record = _prepare_candidate(finding)
            guarded.append(item)
            records.append(record)
            sources[str(item[CANDIDATE_ID_FIELD])] = item

        ranked = original(guarded, config)
        restored: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        for finding in ranked:
            if not isinstance(finding, dict):
                continue
            candidate_id = str(finding.get(CANDIDATE_ID_FIELD, "") or "")
            source = sources.get(candidate_id)
            if source is not None and source.get(SEMANTIC_KEY_FIELD):
                finding = _restore_semantic_candidate(finding, source)
            restored.append(finding)
            if candidate_id:
                selected_ids.add(candidate_id)

        for record in records:
            record["selected_by_ranker"] = record["candidate_id"] in selected_ids
        writer = getattr(module.hardened, "write_debug_json_artifact_safely", None)
        if callable(writer):
            writer(
                config,
                SELECTION_ARTIFACT_PATH,
                {
                    "schema_version": "dcoir_review_v51_candidate_integrity_v1",
                    "version": VERSION,
                    "input_candidate_count": len(guarded),
                    "selected_candidate_count": len(restored),
                    "candidates": records,
                    "selected": [_snapshot_candidate(item) for item in restored],
                },
            )
        return restored

    module.rank_findings_for_required_budget = rank_findings_for_required_budget


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
    raw = _raw_key(finding.get("_risk_sentinel_key"))
    if raw is not None:
        try:
            if v16._coverage_key(raw) in required_coverage:
                return True
        except Exception:
            pass
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
        raise RuntimeError("DCOIR v51 could not locate final required-sentinel selector")

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
            if isinstance(item, dict) and _raw_key(item.get(SEMANTIC_KEY_FIELD)) is not None
        ]
        selected_ids = {
            str(item.get(CANDIDATE_ID_FIELD, "") or "")
            for item in selected
            if isinstance(item, dict) and str(item.get(CANDIDATE_ID_FIELD, "") or "")
        }
        required_coverage = _sentinel_coverage(risk_sentinels)
        dispositions: list[dict[str, Any]] = []

        for source in protected:
            candidate_id = str(source.get(CANDIDATE_ID_FIELD, "") or "")
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
                    item_id = str(item.get(CANDIDATE_ID_FIELD, "") or "")
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
                FINAL_SELECTION_ARTIFACT_PATH,
                {
                    "schema_version": "dcoir_review_v51_final_selection_integrity_v1",
                    "version": VERSION,
                    "inline_limit": limit,
                    "required_sentinel_count": len(required_coverage),
                    "protected_semantic_candidate_count": len(protected),
                    "dispositions": dispositions,
                    "selected": [_snapshot_candidate(item) for item in selected if isinstance(item, dict)],
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
        raise RuntimeError("DCOIR v51 could not locate publication verifier")

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
                    VERIFIER_ARTIFACT_PATH,
                    {
                        "schema_version": "dcoir_review_v51_verifier_candidate_provenance_v1",
                        "head_sha": str(pr.get("head", {}).get("sha", "") or "").strip(),
                        "candidate_count": len(findings),
                        "candidates": [_snapshot_candidate(item) for item in findings if isinstance(item, dict)],
                    },
                )
        return original(review_module, findings, gh, pr, config, reporter)

    v21.verify_findings_for_publication = verify_findings_for_publication


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    _patch_config_loader(module)
    _patch_postable_key()
    _patch_ranker(module)
    _patch_required_selection(module)
    _patch_verifier_debug(module)
    module.DCOIR_SEMANTIC_CANDIDATE_IDENTITY_CONTRACT = (
        "v51: unsupported free-text risk-kind inference may not rewrite or "
        "collision-dedupe an ordinary semantic candidate before verifier input"
    )
    setattr(module, _APPLIED_ATTR, True)
