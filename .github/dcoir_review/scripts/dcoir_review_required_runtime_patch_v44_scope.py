"""Architecture-B v44 deterministic candidate-escalation planning and bounded context."""

from __future__ import annotations

import copy
import json
import math
import os
import re
from pathlib import Path
from typing import Any

CONTRACT = "architecture-b-candidate-escalation-v1"
DEFAULT_CONFIDENCE_MARGIN = 0.10
DEFAULT_MAX_PATHS = 4
DEFAULT_FILE_CHARS = 12000
DEFAULT_TOTAL_CONTEXT_CHARS = 48000

_HISTORICALLY_DIFFICULT_PATH_TERMS = (
    "adjudicat",
    "auth",
    "gate",
    "normaliz",
    "parser",
    "policy",
    "review",
    "router",
    "scor",
    "select",
    "validat",
    "verif",
)
_DEPENDENCY_LANGUAGE = re.compile(
    r"\b(caller|callee|consumer|dependency|dependent|import|loader|sibling|cross[- ]file)\b",
    re.IGNORECASE,
)


def _normal_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _line(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return None
    return parsed


def finding_key(item: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(item.get("path", "") or "").strip(),
        _line(item.get("line")) or 0,
        _normal_text(item.get("title")),
    )


def dedupe_exact_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        key = finding_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _required_uncovered_sentinels(
    module: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
) -> tuple[list[Any], str]:
    hardened = module.hardened
    uncovered = getattr(hardened, "uncovered_risk_sentinels", None)
    if callable(uncovered):
        try:
            return list(uncovered(findings, risk_sentinels, config)), ""
        except Exception:
            return [], "risk-sentinel-classifier-error"

    required = getattr(hardened, "required_risk_sentinels", None)
    covers = getattr(hardened, "finding_covers_risk_sentinel", None)
    if not callable(required) or not callable(covers):
        return [], "risk-sentinel-classifier-unavailable"
    try:
        required_items = list(required(risk_sentinels))
        return [
            sentinel
            for sentinel in required_items
            if not any(covers(item, sentinel) for item in findings)
        ], ""
    except Exception:
        return [], "risk-sentinel-classifier-error"


def _finding_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field, "") or "")
        for field in ("title", "body", "validation", "suggested_replacement")
    )


def _mentioned_changed_paths(
    item: dict[str, Any],
    changed_paths: set[str],
) -> tuple[set[str], bool]:
    own_path = str(item.get("path", "") or "").strip()
    text = _finding_text(item)
    lower = text.lower()
    mentioned: set[str] = set()
    for path in changed_paths:
        if path == own_path:
            continue
        if path.lower() in lower:
            mentioned.add(path)
            continue
        basename = Path(path).name.lower()
        if basename and basename in lower:
            mentioned.add(path)
    unresolved_dependency = bool(_DEPENDENCY_LANGUAGE.search(text)) and not mentioned
    return mentioned, unresolved_dependency


def _path_is_historically_difficult(path: str) -> bool:
    lowered = path.lower()
    return any(term in lowered for term in _HISTORICALLY_DIFFICULT_PATH_TERMS)


def _plan(
    mode: str,
    reasons: list[str],
    findings: list[dict[str, Any]],
    selected_paths: set[str] | list[str],
    escalated_keys: list[list[Any]],
    uncovered_paths: list[str],
) -> dict[str, Any]:
    if mode in {"broader-context", "full-deep"}:
        escalated_keys = [list(finding_key(item)) for item in findings]
    return {
        "contract": CONTRACT,
        "mode": mode,
        "reasons": reasons,
        "candidate_count": len(findings),
        "deduped_candidate_count": len(findings),
        "selected_paths": sorted(selected_paths),
        "escalated_candidate_keys": escalated_keys,
        "uncovered_risk_paths": uncovered_paths,
    }


def build_escalation_plan(
    module: Any,
    result: dict[str, Any],
    files: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
    review_mode: str,
) -> dict[str, Any]:
    raw_findings = module.hardened.result_findings(result)
    findings = dedupe_exact_findings(
        [item for item in raw_findings if isinstance(item, dict)]
    )
    changed_paths = {
        str(item.get("filename", "") or "").strip()
        for item in files
        if str(item.get("filename", "") or "").strip()
        and str(item.get("status", "") or "").lower() not in {"removed", "deleted"}
    }
    minimum = _confidence(getattr(config, "minimum_confidence", 0.70))
    margin = _confidence(
        getattr(config, "candidate_escalation_confidence_margin", DEFAULT_CONFIDENCE_MARGIN)
    )
    try:
        max_paths = max(
            1, int(getattr(config, "candidate_escalation_max_paths", DEFAULT_MAX_PATHS))
        )
    except (TypeError, ValueError):
        return _plan(
            "broader-context",
            ["invalid-escalation-path-budget"],
            findings,
            changed_paths,
            [],
            [],
        )
    if minimum is None or margin is None:
        return _plan(
            "broader-context",
            ["invalid-escalation-threshold-config"],
            findings,
            changed_paths,
            [],
            [],
        )

    if review_mode == "deep-forced":
        return _plan(
            "full-deep",
            ["explicit-deep-mode"],
            findings,
            changed_paths,
            [list(finding_key(item)) for item in findings],
            [],
        )
    if review_mode != "first-pass-deep":
        return _plan(
            "not-applicable",
            ["review-mode-not-deep"],
            findings,
            [],
            [],
            [],
        )

    uncovered, sentinel_error = _required_uncovered_sentinels(
        module, findings, risk_sentinels, config
    )
    if sentinel_error:
        return _plan(
            "broader-context",
            [sentinel_error],
            findings,
            changed_paths,
            [],
            [],
        )

    reasons: set[str] = set()
    selected_paths: set[str] = {
        str(getattr(item, "path", "") or "").strip()
        for item in uncovered
        if str(getattr(item, "path", "") or "").strip()
    }
    uncovered_paths = sorted(selected_paths)
    if selected_paths:
        reasons.add("uncovered-required-risk-sentinel")

    difficult_paths = {path for path in changed_paths if _path_is_historically_difficult(path)}
    if difficult_paths:
        selected_paths.update(difficult_paths)
        reasons.add("historically-difficult-changed-surface")

    escalated_keys: list[list[Any]] = []
    for item in findings:
        path = str(item.get("path", "") or "").strip()
        line = _line(item.get("line"))
        if not path or path not in changed_paths or line is None:
            return _plan(
                "broader-context",
                ["candidate-anchor-ambiguous"],
                findings,
                changed_paths,
                [],
                uncovered_paths,
            )

        candidate_reasons: set[str] = set()
        confidence = _confidence(item.get("confidence"))
        if confidence is None:
            candidate_reasons.add("missing-or-invalid-confidence")
        elif confidence <= min(1.0, minimum + margin):
            candidate_reasons.add("near-publication-threshold")

        severity = str(item.get("severity", "") or "").strip().lower()
        if severity in {"critical", "high"}:
            candidate_reasons.add("high-risk-severity")

        if path in selected_paths:
            candidate_reasons.add("risk-or-difficult-surface")

        if sum(finding_key(other)[:2] == (path, line) for other in findings) > 1:
            candidate_reasons.add("conflicting-candidate-hypotheses")

        mentioned, unresolved_dependency = _mentioned_changed_paths(item, changed_paths)
        if mentioned:
            candidate_reasons.add("explicit-cross-file-dependency")
            selected_paths.update(mentioned)
        elif unresolved_dependency:
            return _plan(
                "broader-context",
                ["unresolved-cross-file-dependency"],
                findings,
                changed_paths,
                [],
                uncovered_paths,
            )

        if candidate_reasons:
            selected_paths.add(path)
            reasons.update(candidate_reasons)
            escalated_keys.append(list(finding_key(item)))

    if len(selected_paths) > max_paths:
        return _plan(
            "broader-context",
            ["scoped-path-budget-exceeded"],
            findings,
            changed_paths,
            escalated_keys,
            uncovered_paths,
        )

    if not selected_paths:
        return _plan(
            "none",
            ["confident-low-risk-primary-evidence"],
            findings,
            [],
            [],
            [],
        )

    return _plan(
        "candidate-scoped",
        sorted(reasons),
        findings,
        selected_paths,
        escalated_keys,
        uncovered_paths,
    )


def scoped_findings(
    findings: list[dict[str, Any]],
    selected_paths: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped: list[dict[str, Any]] = []
    passthrough: list[dict[str, Any]] = []
    for item in dedupe_exact_findings(findings):
        target = scoped if str(item.get("path", "") or "") in selected_paths else passthrough
        target.append(item)
    return scoped, passthrough


def build_bounded_evidence(
    module: Any,
    gh: Any,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    config: Any,
    risk_sentinels: list[Any],
    selected_paths: set[str],
) -> tuple[str | None, str]:
    file_map = {
        str(item.get("filename", "") or "").strip(): item
        for item in files
        if str(item.get("filename", "") or "").strip()
    }
    scoped_files: list[dict[str, Any]] = []
    for path in sorted(selected_paths):
        item = file_map.get(path)
        if not isinstance(item, dict):
            return None, "selected-path-missing-from-pr-files"
        if str(item.get("status", "") or "").lower() in {"removed", "deleted"}:
            return None, "selected-path-not-readable-at-head"
        scoped_files.append(item)

    context_config = copy.copy(config)
    context_config.per_file_review_max_files = max(
        len(scoped_files),
        int(getattr(config, "candidate_escalation_max_paths", DEFAULT_MAX_PATHS)),
    )
    contexts = module.build_file_contexts(gh, pr, scoped_files, context_config)
    by_path = {str(item.get("path", "") or ""): item for item in contexts}
    if set(by_path) != set(selected_paths):
        return None, "selected-head-context-unavailable"

    try:
        file_chars = max(
            1000, int(getattr(config, "candidate_escalation_file_chars", DEFAULT_FILE_CHARS))
        )
        total_chars = max(
            file_chars,
            int(
                getattr(
                    config,
                    "candidate_escalation_total_context_chars",
                    DEFAULT_TOTAL_CONTEXT_CHARS,
                )
            ),
        )
    except (TypeError, ValueError):
        return None, "invalid-bounded-context-budget"

    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    chunks = [
        f"Repository: {module.base.sanitize_text(os.environ.get('GITHUB_REPOSITORY', ''), config)}",
        f"PR number: {pr.get('number')}",
        f"PR title: {module.base.sanitized_prompt_value(pr.get('title'), config)}",
        f"Exact reviewed HEAD: {head_sha}",
        "Candidate-scoped exact-head evidence follows. Do not assume facts outside this package.",
    ]
    used = sum(len(item) for item in chunks)

    for path in sorted(selected_paths):
        item = file_map[path]
        context = by_path[path]
        patch = module.base.sanitize_text(str(item.get("patch", "") or ""), config)
        text = module.base.sanitize_text(str(context.get("text", "") or ""), config)
        if len(text) > file_chars:
            text = text[:file_chars] + "\n[head-file context truncated by v44 candidate budget]"
        sentinels = [
            sentinel for sentinel in risk_sentinels if getattr(sentinel, "path", "") == path
        ]
        sentinel_text = (
            module.hardened.risk_sentinel_block(sentinels, config)
            if sentinels
            else "No deterministic risk anchors detected for this scoped file."
        )
        chunk = (
            f"\n\n### Scoped file: {path}\n"
            f"{sentinel_text}\n\n"
            f"Changed patch:\n```diff\n{patch}\n```\n\n"
            f"Exact-head file context:\n```text\n{text}\n```"
        )
        if used + len(chunk) > total_chars:
            return None, "bounded-context-budget-insufficient"
        chunks.append(chunk)
        used += len(chunk)

    return "\n".join(chunks), ""


def candidate_digest(findings: list[dict[str, Any]], max_chars: int) -> str:
    compact = [
        {
            "path": str(item.get("path", "") or "")[:220],
            "line": item.get("line", 0),
            "severity": str(item.get("severity", "") or "")[:16],
            "confidence": item.get("confidence"),
            "title": str(item.get("title", "") or "")[:180],
            "body": str(item.get("body", "") or "")[:360],
            "validation": str(item.get("validation", "") or "")[:240],
        }
        for item in dedupe_exact_findings(findings)
    ]
    text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= max_chars:
        return text
    identity = [
        {
            "path": item["path"][:100],
            "line": item["line"],
            "title": item["title"][:80],
        }
        for item in compact
    ]
    text = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    if len(text) > max_chars:
        raise ValueError("DCOIR v44 candidate digest budget cannot represent scoped candidates")
    return text
