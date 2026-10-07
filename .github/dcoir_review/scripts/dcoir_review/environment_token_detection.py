"""Stable environment-token callback detection for DCOIR Review.

This owner preserves cross-line Python and PowerShell detection where an
environment-derived token is read shortly before it is forwarded to an
outbound/request-controlled callback. It also keeps required sentinel kinds
front-loaded when an anchor budget is applied. Historical v5 compatibility
helpers still define the shared sentinel kind taxonomy, but production no
longer needs the historical final-apply runtime installer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review.risk_sentinel_policy as v5


APPLIED_MARKER = "_dcoir_review_environment_token_detection_applied"


def _sentinel_line(value: Any) -> int:
    try:
        return int(getattr(value, "line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    seen: set[tuple[str, int, str]] = set()
    result: list[Any] = []
    for sentinel in sentinels:
        key = (
            str(getattr(sentinel, "path", "") or ""),
            _sentinel_line(sentinel),
            v5._sentinel_kind(sentinel),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(sentinel)
    return result


def make_environment_token_sentinels(hardened: Any, diff: str) -> list[Any]:
    iter_added = getattr(hardened, "iter_added_diff_lines", None)
    risk_sentinel_type = getattr(hardened, "RiskSentinel", None)
    if not callable(iter_added) or risk_sentinel_type is None:
        return []

    by_path: dict[str, list[Any]] = {}
    for changed_line in iter_added(diff):
        path = str(getattr(changed_line, "path", "") or "")
        text = str(getattr(changed_line, "text", "") or "")
        is_comment = getattr(hardened, "is_comment_only_added_line", None)
        if callable(is_comment) and is_comment(path, text):
            continue
        by_path.setdefault(path, []).append(changed_line)

    sentinels: list[Any] = []
    for path, lines in by_path.items():
        suffix = Path(path.lower()).suffix
        if suffix == ".py":
            env_lines = [
                line
                for line in lines
                if v5.PY_ENV_RE.search(str(getattr(line, "text", "") or ""))
            ]
            if not env_lines:
                continue
            for candidate in lines:
                candidate_text = str(getattr(candidate, "text", "") or "")
                if not v5.OUTBOUND_RE.search(candidate_text):
                    continue
                nearby_env = next(
                    (
                        env
                        for env in env_lines
                        if 0 <= _sentinel_line(candidate) - _sentinel_line(env) <= 8
                    ),
                    None,
                )
                if nearby_env is None:
                    continue
                combined_text = f"{getattr(nearby_env, 'text', '')} {candidate_text}"
                sentinels.append(
                    risk_sentinel_type(
                        path=path,
                        line=_sentinel_line(candidate),
                        label="DCOIR Python environment token callback",
                        detail="environment token read from env and forwarded to request-controlled callback",
                        text=combined_text,
                    )
                )
                break
        elif suffix in {".ps1", ".psm1", ".psd1"}:
            env_lines = [
                line
                for line in lines
                if v5.PS_ENV_RE.search(str(getattr(line, "text", "") or ""))
            ]
            if not env_lines:
                continue
            for candidate in lines:
                candidate_text = str(getattr(candidate, "text", "") or "")
                if not v5.OUTBOUND_RE.search(candidate_text):
                    continue
                nearby_env = next(
                    (
                        env
                        for env in env_lines
                        if 0 <= _sentinel_line(candidate) - _sentinel_line(env) <= 4
                    ),
                    None,
                )
                if nearby_env is None:
                    continue
                combined_text = f"{getattr(nearby_env, 'text', '')} {candidate_text}"
                sentinels.append(
                    risk_sentinel_type(
                        path=path,
                        line=_sentinel_line(candidate),
                        label="DCOIR PowerShell environment token callback",
                        detail="environment token read from env and forwarded to request-controlled callback",
                        text=combined_text,
                    )
                )
                break
    return _dedupe_sentinels(sentinels)


def select_required_first(sentinels: list[Any], max_anchors: int | None) -> list[Any]:
    deduped = _dedupe_sentinels(sentinels)
    if max_anchors is None or len(deduped) <= max_anchors:
        return deduped

    selected: list[Any] = []
    seen: set[tuple[str, int, str]] = set()

    def add(sentinel: Any) -> None:
        key = (
            str(getattr(sentinel, "path", "") or ""),
            _sentinel_line(sentinel),
            v5._sentinel_kind(sentinel),
        )
        if key not in seen and len(selected) < max_anchors:
            seen.add(key)
            selected.append(sentinel)

    for kind in v5.REQUIRED_KIND_ORDER:
        for sentinel in deduped:
            if v5._sentinel_kind(sentinel) == kind:
                add(sentinel)
                break
    for sentinel in deduped:
        add(sentinel)
    return selected



def build_detector(hardened: Any, next_detect: Any):
    """Compose cross-line environment-token detection around ``next_detect``."""
    if not callable(next_detect):
        raise RuntimeError("DCOIR environment-token detection requires a callable detector")

    def detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
        try:
            existing = list(next_detect(diff, None))
        except TypeError:
            existing = list(next_detect(diff))
        return select_required_first(
            [*existing, *make_environment_token_sentinels(hardened, diff)],
            max_anchors,
        )

    return detect_risk_sentinels

def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    original_detect = getattr(module, "detect_risk_sentinels", None)
    if not callable(original_detect):
        return
    detector = build_detector(hardened, original_detect)
    module.detect_risk_sentinels = detector
    hardened.detect_risk_sentinels = detector
    hardened.select_risk_sentinels = select_required_first
    setattr(module, APPLIED_MARKER, True)
