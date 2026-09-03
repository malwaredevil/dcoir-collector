"""Architecture-B v45 verifier-authoritative publication overlay.

The semantic detector summary is a hypothesis, not a publication verdict.  This
post-terminal layer records the exact-head v21 verifier disposition and builds
the final GitHub review body only from that disposition plus the final repaired
finding set.  Unanchored hypotheses and legacy overflow prose cannot bypass the
publication verifier.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v21 as v21


VERSION = "v45"
SCHEMA_VERSION = "dcoir_review_final_publication_disposition_v1"
_APPLIED_ATTR = "_dcoir_v45_applied"
_CONFIG_STORAGE = "_dcoir_v45_original_load_pareto_context_config"
_BODY_STORAGE = "_dcoir_v45_original_build_review_body_with_unanchored"
_VERIFIER_STORAGE = "_dcoir_v45_original_verify_findings_for_publication"
_DISPOSITION_ATTR = "_dcoir_v45_verifier_disposition"
ARTIFACT_PATH = "metadata/final-publication-disposition-v45.json"


def _head_sha(pr: Any) -> str:
    if not isinstance(pr, dict):
        return ""
    head = pr.get("head")
    if not isinstance(head, dict):
        return ""
    return str(head.get("sha", "") or "").strip()


def _dict_findings(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, _CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, _CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v45 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.verifier_authoritative_publication_review = module.hardened.bool_value(
            data, "verifier_authoritative_publication_review", True
        )
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _capture_verifier_disposition(
    module: Any,
    candidates: list[dict[str, Any]],
    verified: list[dict[str, Any]],
    pr: dict[str, Any],
) -> dict[str, Any]:
    head_sha = _head_sha(pr)
    disposition = {
        "schema_version": SCHEMA_VERSION,
        "reviewed_head_sha": head_sha,
        "verifier_candidate_count": len(_dict_findings(candidates)),
        "verifier_supported_count": len(_dict_findings(verified)),
    }
    disposition["verifier_suppressed_count"] = max(
        0,
        disposition["verifier_candidate_count"]
        - disposition["verifier_supported_count"],
    )
    setattr(module, _DISPOSITION_ATTR, disposition)
    return disposition


def _patch_verifier(module: Any) -> None:
    original = getattr(v21, _VERIFIER_STORAGE, None)
    if original is None:
        original = getattr(v21, "verify_findings_for_publication", None)
        if callable(original):
            setattr(v21, _VERIFIER_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v45 could not locate the v21 publication verifier")

    def verify_findings_for_publication(
        review_module: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        verified = original(review_module, findings, gh, pr, config, reporter)
        _capture_verifier_disposition(review_module, findings, verified, pr)
        return verified

    v21.verify_findings_for_publication = verify_findings_for_publication


def _verified_for_head(finding: dict[str, Any], reviewed_commit: str) -> bool:
    verifier = finding.get(v21.VERIFIER_MARKER)
    return bool(
        isinstance(verifier, dict)
        and verifier.get("supported") is True
        and str(verifier.get("head_sha", "") or "").strip() == reviewed_commit
    )


def _coverage_counts() -> dict[str, int]:
    core = getattr(v16, "core", None)
    summary = getattr(core, "SELECTION_SUMMARY", {}) if core is not None else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "aggregate_covered_required_count": len(
            _dict_findings(summary.get("aggregate_covered_sentinels", []))
        ),
        "unpublished_required_signal_count": len(
            _dict_findings(summary.get("omitted_required_sentinels", []))
        ),
        "unpublished_optional_signal_count": len(
            _dict_findings(summary.get("omitted_optional_high_risk_sentinels", []))
        ),
        "unpublished_detector_signal_count": len(
            _dict_findings(summary.get("detector_only_high_risk_overflow", []))
        ),
    }


def _final_disposition(
    module: Any,
    result: dict[str, Any],
    findings: list[dict[str, Any]],
    unanchored_findings: list[dict[str, Any]],
    reviewed_commit: str,
) -> dict[str, Any]:
    if not reviewed_commit:
        raise module.hardened.ReviewQualityError(
            "DCOIR v45 publication could not determine the reviewed PR head SHA"
        )
    verifier = getattr(module, _DISPOSITION_ATTR, None)
    if not isinstance(verifier, dict):
        raise module.hardened.ReviewQualityError(
            "DCOIR v45 publication is missing the final verifier disposition"
        )
    if str(verifier.get("reviewed_head_sha", "") or "").strip() != reviewed_commit:
        raise module.hardened.ReviewQualityError(
            "DCOIR v45 verifier disposition does not match the reviewed PR head"
        )
    published = _dict_findings(findings)
    if any(not _verified_for_head(item, reviewed_commit) for item in published):
        raise module.hardened.ReviewQualityError(
            "DCOIR v45 refused to publish a finding without exact-head verifier support"
        )
    verifier_supported = int(verifier.get("verifier_supported_count", 0) or 0)
    raw_findings = _dict_findings(result.get("findings", [])) if isinstance(result, dict) else []
    disposition = {
        **verifier,
        **_coverage_counts(),
        "raw_model_candidate_count": len(raw_findings),
        "published_finding_count": len(published),
        "downstream_suppressed_count": max(0, verifier_supported - len(published)),
        "unanchored_hypothesis_count": len(_dict_findings(unanchored_findings)),
        "unanchored_disposition": "unpublished-unverified",
        "model_summary_discarded": bool(str(result.get("summary", "") or "").strip())
        if isinstance(result, dict)
        else False,
    }
    return disposition


def _render_body(module: Any, disposition: dict[str, Any], reviewed_commit: str) -> str:
    published = int(disposition["published_finding_count"])
    intro = (
        "Verifier-supported findings were published for this pull request."
        if published
        else "No verifier-supported findings were published for this pull request."
    )
    lines = [
        module.base.MARKER,
        f"💡 {module.base.REVIEW_DISPLAY_NAME}",
        intro,
        "",
        f"Reviewed commit: `{module.base.short_commit(reviewed_commit)}`",
        "",
        "### Verified publication disposition",
        f"- Published findings: `{published}`",
        f"- Verifier candidates: `{disposition['verifier_candidate_count']}`",
        f"- Verifier-supported candidates: `{disposition['verifier_supported_count']}`",
        f"- Verifier-suppressed candidates: `{disposition['verifier_suppressed_count']}`",
        f"- Post-verifier suppressions: `{disposition['downstream_suppressed_count']}`",
        f"- Unanchored hypotheses not published: `{disposition['unanchored_hypothesis_count']}`",
    ]
    unpublished = sum(
        int(disposition[key])
        for key in (
            "unpublished_required_signal_count",
            "unpublished_optional_signal_count",
            "unpublished_detector_signal_count",
        )
    )
    if unpublished:
        lines.extend(
            [
                f"- Deterministic risk signals not published as verified findings: `{unpublished}`",
                "",
                "Unpublished signals remain diagnostic evidence only; they are not presented as actionable findings.",
            ]
        )
    lines.extend(
        [
            "",
            "Result: Final prose was generated from the exact-head verified disposition; model-authored summary text was not published.",
        ]
    )
    return module.base.github_safe_body("\n".join(lines).strip(), limit=12000)


def _patch_review_body(module: Any) -> None:
    original = getattr(module, _BODY_STORAGE, None)
    if original is None:
        original = getattr(module.hardened, "build_review_body_with_unanchored", None)
        if callable(original):
            setattr(module, _BODY_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v45 could not locate the final review-body builder")

    def build_review_body_with_unanchored(
        result: dict[str, Any],
        findings: list[dict[str, Any]],
        unanchored_findings: list[dict[str, Any]],
        model_used: str,
        config: Any,
        reviewed_commit: str = "",
    ) -> str:
        if not bool(getattr(config, "verifier_authoritative_publication_review", False)):
            return original(
                result,
                findings,
                unanchored_findings,
                model_used,
                config,
                reviewed_commit,
            )
        disposition = _final_disposition(
            module, result, findings, unanchored_findings, reviewed_commit
        )
        module.hardened.write_debug_json_artifact_safely(
            config, ARTIFACT_PATH, disposition
        )
        return _render_body(module, disposition, reviewed_commit)

    module.hardened.build_review_body_with_unanchored = build_review_body_with_unanchored


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    _patch_config_loader(module)
    _patch_verifier(module)
    _patch_review_body(module)
    setattr(module, _APPLIED_ATTR, True)
