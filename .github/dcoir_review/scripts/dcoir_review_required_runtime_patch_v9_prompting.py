"""Prompt-accounting and comment rendering hooks for DCOIR Review v9."""

from __future__ import annotations

import re
from typing import Any

import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v6 as v6

from dcoir_review_required_runtime_patch_v9_core import (
    EVENT_LIMIT,
    INLINE_MODEL_FOOTER_RE,
    PARETO_CALL_EVENTS,
    PROMPT_REVIEW_CALLS,
    PROMPT_REVIEW_EVENTS,
    PROMPT_REVIEW_FAILURES,
    SELECTION_SUMMARY,
    _postable_key,
    _validation_for_key,
    _yaml_load_arg,
)

def _prompt_sha(prompt: str) -> str:
    return v6._sha12(prompt)


def _prompt_review_summary() -> dict[str, Any]:
    return {
        "prompt_review_events": list(PROMPT_REVIEW_EVENTS),
        "prompt_review_calls": list(PROMPT_REVIEW_CALLS),
        "pareto_call_events": list(PARETO_CALL_EVENTS),
    }


def _write_prompt_review_summary(hardened: Any, config: Any) -> None:
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/prompt-review-summary-v9.json", _prompt_review_summary())


def _record_prompt_review_event(prompt_kind: str, metadata: dict[str, Any], original_prompt: str = "") -> None:
    PROMPT_REVIEW_EVENTS.append(
        {
            "prompt_kind": prompt_kind,
            "prompt_sha": _prompt_sha(original_prompt) if original_prompt else metadata.get("prompt_sha", ""),
            "accepted": bool(metadata.get("accepted", False)),
            "fallback_to_original": bool(metadata.get("fallback_to_original", False)),
            "addendum_chars": int(metadata.get("addendum_chars", 0) or 0),
            "fallback_reason": metadata.get("fallback_reason", ""),
            "error": metadata.get("error", ""),
            "model": metadata.get("model", v6.PROMPT_REVIEW_MODEL),
            "model_used": metadata.get("model_used", ""),
        }
    )
    del PROMPT_REVIEW_EVENTS[:-EVENT_LIMIT]


def _record_prompt_review_call(prompt: str, reviewed_prompt: str, error: str = "") -> None:
    PROMPT_REVIEW_CALLS.append(
        {
            "prompt_kind": v6._prompt_kind(prompt),
            "prompt_sha": _prompt_sha(prompt),
            "changed": bool(reviewed_prompt and reviewed_prompt != prompt),
            "error": error,
        }
    )
    del PROMPT_REVIEW_CALLS[:-EVENT_LIMIT]


def _patch_prompt_review_call_accounting() -> None:
    original = getattr(v6, "_dcoir_required_v9_original_review_prompt_once", None)
    if original is None:
        original = getattr(v6, "_review_prompt_once", None)
        v6._dcoir_required_v9_original_review_prompt_once = original
    if not callable(original):
        return

    def review_prompt_once(original_prompt: str, config: Any, hardened: Any, base: Any) -> str:
        if hasattr(v6, "_prompt_review_cache"):
            v6._prompt_review_cache.pop(f"{v6._prompt_kind(original_prompt)}:{_prompt_sha(original_prompt)}", None)
        try:
            reviewed = original(original_prompt, config, hardened, base)
        except Exception as exc:
            _record_prompt_review_call(original_prompt, "", f"{type(exc).__name__}: {exc}")
            _write_prompt_review_summary(hardened, config)
            raise
        _record_prompt_review_call(original_prompt, reviewed)
        _write_prompt_review_summary(hardened, config)
        return reviewed

    v6._review_prompt_once = review_prompt_once


def _prompt_records_for(prompt: str) -> tuple[bool, bool]:
    kind = v6._prompt_kind(prompt)
    digest = _prompt_sha(prompt)
    call = any(item.get("prompt_kind") == kind and item.get("prompt_sha") == digest for item in PROMPT_REVIEW_CALLS)
    event = any(item.get("prompt_kind") == kind and item.get("prompt_sha") == digest for item in PROMPT_REVIEW_EVENTS)
    return call, event


def _record_target_call(prompt: str, model: str, before_calls: int, before_events: int, error: str = "") -> None:
    call, event = _prompt_records_for(prompt)
    record = {
        "model": model,
        "prompt_kind": v6._prompt_kind(prompt),
        "prompt_sha": _prompt_sha(prompt),
        "prompt_review_call_recorded": call,
        "prompt_review_debug_event_recorded": event,
        "prompt_review_call_count_delta": len(PROMPT_REVIEW_CALLS) - before_calls,
        "prompt_review_event_count_delta": len(PROMPT_REVIEW_EVENTS) - before_events,
        "error": error,
    }
    PARETO_CALL_EVENTS.append(record)
    del PARETO_CALL_EVENTS[:-EVENT_LIMIT]
    if not call or not event:
        PROMPT_REVIEW_FAILURES.append(record)


def _prompt_review_problem() -> str:
    missing = [item for item in PROMPT_REVIEW_FAILURES if not item.get("prompt_review_call_recorded") or not item.get("prompt_review_debug_event_recorded")]
    if not missing:
        return ""
    details = "; ".join(
        f"{item.get('prompt_kind')} {item.get('model')} call_delta={item.get('prompt_review_call_count_delta')} event_delta={item.get('prompt_review_event_count_delta')}"
        for item in missing[:5]
    )
    return f"missing OpenRouter Auto prompt-engineering preflight evidence before Pareto call(s): {details}"


def _ensure_prompt_review(config: Any) -> None:
    problem = _prompt_review_problem()
    if problem:
        raise RuntimeError(f"DCOIR Review quality failure: {problem}")


def _patch_prompt_review_readback(hardened: Any, base: Any) -> None:
    original_write = getattr(v6, "_dcoir_required_v9_original_write_prompt_review_debug", None)
    if original_write is None:
        original_write = getattr(v6, "_write_prompt_review_debug", None)
        v6._dcoir_required_v9_original_write_prompt_review_debug = original_write
    if callable(original_write):

        def write_prompt_review_debug(hardened_arg: Any, config: Any, prompt_kind: str, original_prompt: str, candidate_prompt: str, metadata: dict[str, Any]) -> None:
            _record_prompt_review_event(prompt_kind, metadata, original_prompt)
            _write_prompt_review_summary(hardened, config)
            if callable(getattr(base, "emit_status", None)):
                outcome = "accepted addendum" if metadata.get("accepted") else "kept original"
                if metadata.get("error"):
                    outcome = "error; kept original"
                reason = metadata.get("fallback_reason", "")
                base.emit_status(
                    "prompt-engineering",
                    f"openrouter/auto reviewed {prompt_kind} before Pareto call; {outcome}"
                    + (f"; reason={reason}" if reason else "")
                    + f"; addendum_chars={metadata.get('addendum_chars', 0)}",
                )
            original_write(hardened_arg, config, prompt_kind, original_prompt, candidate_prompt, metadata)

        v6._write_prompt_review_debug = write_prompt_review_debug


def _patch_target_call_accounting(hardened: Any) -> None:
    original = getattr(hardened, "_dcoir_required_v9_original_openrouter_request_once", None)
    if original is None:
        original = getattr(hardened, "openrouter_request_once", None)
        hardened._dcoir_required_v9_original_openrouter_request_once = original
    if not callable(original):
        return

    def openrouter_request_once(prompt: str, schema: dict[str, Any], config: Any, ignored_providers: list[str], model: str) -> tuple[dict[str, Any], str, str]:
        target = str(model or "") != v6.PROMPT_REVIEW_MODEL and (
            "pareto" in str(model or "").lower() or bool(v6._should_review_model(model, config))
        )
        before_calls = len(PROMPT_REVIEW_CALLS)
        before_events = len(PROMPT_REVIEW_EVENTS)
        try:
            result = original(prompt, schema, config, ignored_providers, model)
        except Exception as exc:
            if target:
                _record_target_call(prompt, model, before_calls, before_events, f"{type(exc).__name__}: {exc}")
                _write_prompt_review_summary(hardened, config)
            raise
        if target:
            _record_target_call(prompt, model, before_calls, before_events)
            _write_prompt_review_summary(hardened, config)
        return result

    hardened.openrouter_request_once = openrouter_request_once


def _patch_progress_comment(base: Any, hardened: Any | None = None) -> None:
    owner = base if hasattr(base, "ProgressReporter") else hardened if hasattr(hardened, "ProgressReporter") else None
    reporter = getattr(owner, "ProgressReporter", None) if owner is not None else None
    if reporter is None:
        return
    original_complete = getattr(reporter, "_dcoir_required_v9_original_complete", None)
    if original_complete is None:
        original_complete = getattr(reporter, "complete", None)
        reporter._dcoir_required_v9_original_complete = original_complete
    if callable(original_complete):

        def complete(self: Any, model_used: str, findings_count: int, review_event: str) -> None:
            self._dcoir_reviewed_model = model_used
            _ensure_prompt_review(self.config)
            return original_complete(self, model_used, findings_count, review_event)

        reporter.complete = complete
    original_body = getattr(reporter, "_body", None)
    if not callable(original_body):
        return

    def body(self: Any, state: str, final_lines: list[str] | None = None) -> str:
        rendered = original_body(self, state, final_lines)
        if not getattr(self.config, "debug", False):
            return rendered
        covered = sum(
            1
            for item in PARETO_CALL_EVENTS
            if item.get("prompt_review_call_recorded") and item.get("prompt_review_debug_event_recorded")
        )
        lines = ["", "Prompt engineering:", f"- Pareto calls with OpenRouter Auto preflight evidence: `{covered}/{len(PARETO_CALL_EVENTS)}`."]
        problem = _prompt_review_problem()
        if problem:
            lines.append(f"- Prompt-engineering quality failure: {base.sanitize_public_identity(problem)}.")
        elif not PARETO_CALL_EVENTS:
            lines.append("- Pareto calls observed: `0`.")
        for item in PROMPT_REVIEW_EVENTS[-12:]:
            outcome = "accepted addendum" if item.get("accepted") else "kept original"
            if item.get("error"):
                outcome = "error; kept original"
            reason = str(item.get("fallback_reason", "") or "")
            lines.append(
                "- `openrouter/auto`: "
                f"{item.get('prompt_kind', 'prompt')} before Pareto call; {outcome}; "
                f"addendum_chars=`{item.get('addendum_chars', 0)}`"
                + (f"; reason=`{base.sanitize_public_identity(reason)}`" if reason else "")
                + "."
            )
        omitted = list(SELECTION_SUMMARY.get("omitted_sentinels") or [])
        if omitted:
            lines.extend(
                [
                    "",
                    "Selection overflow:",
                    f"- Omitted high-risk changed-line signals: `{len(omitted)}`.",
                ]
            )
            for item in omitted[:12]:
                path = base.sanitize_public_identity(str(item.get("path", "") or ""))
                line = item.get("line", "")
                kind = base.sanitize_public_identity(str(item.get("kind", "") or ""))
                reason = base.sanitize_public_identity(str(item.get("reason", "") or ""))
                label = base.sanitize_public_identity(str(item.get("label", "") or ""))
                bucket = base.sanitize_public_identity(str(item.get("priority_bucket", "") or ""))
                lines.append(f"- `{path}:{line}` `{kind}` bucket=`{bucket}` reason=`{reason}` label=`{label}`.")
        return base.github_safe_body(f"{rendered.rstrip()}\n" + "\n".join(lines), limit=20000)

    reporter._body = body


def _strip_footer(body: str) -> str:
    text = str(body or "").rstrip()
    patterns = (
        INLINE_MODEL_FOOTER_RE,
        re.compile(r"\n{0,2}<sub>\s*DCOIR Review\s*</sub>\s*$", re.I),
        re.compile(r"\n{0,2}(?:_|\*)?DCOIR Review(?:_|\*)?\s*$", re.I),
    )
    while True:
        previous = text
        for pattern in patterns:
            text = pattern.sub("", text.rstrip()).rstrip()
        if text == previous:
            return text


def _normalize_inline_comment(body: str, finding: dict[str, Any]) -> str:
    text = _strip_footer(body)
    text = re.sub(
        r"^\*\*\s*(?:CRITICAL|HIGH|MEDIUM|LOW)\s*:\s*([^*\n]+?)\s*\*\*",
        r"**\1**",
        text,
        flags=re.I,
    )
    text = re.sub(r"^(?:CRITICAL|HIGH|MEDIUM|LOW)\s*:\s*([^\n]+)", r"\1", text, count=1, flags=re.I)
    text = re.sub(r"\*\*Validation expected after fix:\*\*", "**Validation:**", text, flags=re.I)
    text = re.sub(r"\*\*Validation after fix:\*\*", "**Validation:**", text, flags=re.I)
    text = re.sub(r"(?im)^(\s*)Validation expected after fix:\s*$", r"\1**Validation:**", text)
    text = re.sub(r"(?im)^(\s*)Validation after fix:\s*$", r"\1**Validation:**", text)
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip()
    return text


def _normalize_yaml_identifier(body: str, finding: dict[str, Any]) -> str:
    if _postable_key(finding)[2] != v5.PYTHON_YAML_LOAD:
        return body
    arg = _yaml_load_arg(str(finding.get("_anchored_line_text", "") or ""))
    body = re.sub(r"yaml\.safe_load\([A-Za-z_][A-Za-z0-9_.]*\)", f"yaml.safe_load({arg})", body)
    return re.sub(r"yaml\.load\([A-Za-z_][A-Za-z0-9_.]*,\s*Loader=yaml\.SafeLoader\)", f"yaml.load({arg}, Loader=yaml.SafeLoader)", body)


def _patch_inline_comment(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v9_original_build_inline_comment", None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        base._dcoir_required_v9_original_build_inline_comment = original
    if not callable(original):
        return

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        _ensure_prompt_review(config)
        return _normalize_yaml_identifier(_normalize_inline_comment(original(finding, model_used, config), finding), finding)

    base.build_inline_comment = build_inline_comment


def _patch_validation_text(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v9_original_validation_text_for_finding", None)
    if original is None:
        original = getattr(base, "validation_text_for_finding", None)
        base._dcoir_required_v9_original_validation_text_for_finding = original
    if not callable(original):
        return

    def validation_text_for_finding(finding: dict[str, Any]) -> str:
        path, line, kind = _postable_key(finding)
        return _validation_for_key(kind, path, line) or original(finding)

    base.validation_text_for_finding = validation_text_for_finding
