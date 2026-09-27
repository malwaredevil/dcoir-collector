#!/usr/bin/env python3
"""Closed-contract validation for bounded USB prior-count clarification output."""
from __future__ import annotations

import re
import unicodedata

COUNT_REFERENCE = re.compile(
    r"\b(?:"
    r"how\s+many\s+(?:(?:all\s+)?(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?"
    r"(?:(?:single|overall|combined|total)\s+){0,2}"
    r"(?:(?:all\s+)?(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?"
    r"usb\s+violations?\s+(?:number|count|total)"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?"
    r"(?:(?:single|overall|combined|total)\s+){0,2}"
    r"(?:number|count|total)(?:\s+of)?\s+"
    r"(?:(?:all\s+)?(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r")\b",
    re.I,
)

COUNT_QUALIFIER = re.compile(
    r"\s*\(\s*(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+combined|"
    r"combined\s+(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr))\s*\)",
    re.I,
)
SELF_ACTION_MARKER = re.compile(
    r"\b(?:so\s+(?:i|we)\s+(?:can|will)|so\s+(?:i|we)['’]ll|"
    r"(?:before|after|once)\s+(?:i|we)|"
    r"(?:i|we)(?:['’]ll|\s+will|\s+can))\b",
    re.I,
)
BENIGN_CREATION = re.compile(
    r"^(?:write|prepare|compose|finalize|finish|draft|complete)\s+"
    r"(?:(?:the|a|this|that)\s+)?(?:final\s+)?(?:report|draft|email)$",
    re.I,
)
BENIGN_COUNT_POSSESSION = re.compile(
    r"^(?:get|have)\s+(?:it|the\s+count|"
    r"(?:(?:last|previous)\s+week(?:['’]s)?\s+)?"
    r"(?:(?:single|overall|combined|total)\s+){0,2}count)$",
    re.I,
)
GOVERNED_SURFACE = re.compile(
    r"(?:"
    r"<count> were reported (?:last|previous) week[?.]"
    r"|what was (?:the )?(?:(?:last|previous) week(?:['’]s)? )?(?:(?:single|overall|combined|total) ){0,2}"
    r"<count>(?: (?:reported )?(?:last|previous) week)?(?: <self>)?[?.]"
    r"|(?:(?:please )?(?:provide|give me|let me know)|tell me|could you share) (?:the )?"
    r"(?:(?:last|previous) week(?:['’]s)? )?(?:(?:single|overall|combined|total) ){0,2}"
    r"<count>(?: from (?:last|previous) week)?(?: <self>)?[?.]"
    r"|<self>, what was (?:the )?(?:(?:last|previous) week(?:['’]s)? )?"
    r"(?:(?:single|overall|combined|total) ){0,2}<count>[?.]"
    r"|<self>, <self>[?.]"
    r"|what was (?:the )?(?:(?:last|previous) week(?:['’]s)? )?"
    r"(?:(?:single|overall|combined|total) ){0,2}<count>[?] <self>[.]"
    r")",
    re.I,
)


def _count_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in COUNT_REFERENCE.finditer(text):
        start, end = match.span()
        qualifier = COUNT_QUALIFIER.match(text[end:])
        if qualifier:
            end += qualifier.end()
        spans.append((start, end))
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _mask_count_references(clause: str) -> str:
    masked = clause
    for start, end in reversed(_count_spans(clause)):
        masked = masked[:start] + ' count ' + masked[end:]
    return re.sub(r'\s+', ' ', masked).strip(' ,;.!?')


def _self_action_clauses(text: str) -> tuple[list[tuple[int, int]], list[str]]:
    """Validate every explicit self-action against a closed benign grammar."""
    matches = list(SELF_ACTION_MARKER.finditer(text))
    errors: list[str] = []
    governed_spans: list[tuple[int, int]] = []
    for index, marker in enumerate(matches):
        candidates = [len(text)]
        if index + 1 < len(matches):
            candidates.append(matches[index + 1].start())
        punctuation = re.search(r'[,;.!?]', text[marker.end():])
        if punctuation:
            candidates.append(marker.end() + punctuation.start())
        end = min(candidate for candidate in candidates if candidate >= marker.end())
        body = _mask_count_references(text[marker.end():end])
        if not body:
            errors.append('clarification response contains an incomplete self-action clause')
            continue
        if BENIGN_CREATION.fullmatch(body) or BENIGN_COUNT_POSSESSION.fullmatch(body):
            governed_spans.append((marker.start(), end))
            continue
        errors.append('clarification response requests more than the prior-week overall count: non-governed self-action')
    return governed_spans, errors


def _owned_surface(
    text: str,
    count_spans: list[tuple[int, int]],
    self_action_spans: list[tuple[int, int]],
) -> str:
    """Replace governed spans with typed placeholders and preserve all other syntax."""
    spans = [(start, end, 'count') for start, end in count_spans]
    spans.extend((start, end, 'self') for start, end in self_action_spans)
    merged: list[tuple[int, int, str]] = []
    for start, end, kind in sorted(spans):
        if merged and start <= merged[-1][1]:
            old_start, old_end, old_kind = merged[-1]
            merged[-1] = (
                old_start,
                max(old_end, end),
                'self' if 'self' in (old_kind, kind) else 'count',
            )
        else:
            merged.append((start, end, kind))
    surface = text
    for start, end, kind in reversed(merged):
        surface = surface[:start] + f'<{kind}>' + surface[end:]
    surface = re.sub(r'\s+', ' ', surface).strip()
    return re.sub(r'\s+([,.;!?])', r'\1', surface)


def clarification_content_errors(text: str) -> list[str]:
    normalized = unicodedata.normalize('NFKC', str(text)).replace('\u00a0', ' ')
    lower = re.sub(r'\s+', ' ', normalized.casefold()).strip()
    errors: list[str] = []

    prior_week = bool(re.search(r"\b(?:last|previous)\s+week(?:['’]s)?\b", lower))
    quantity = bool(re.search(r'\b(?:counts?|number|total|overall|combined)\b|\bhow\s+many\b', lower))
    usb = bool(re.search(r'\busb\s+violations?\b', lower))
    if not (prior_week and quantity and usb):
        errors.append('clarification response does not request the missing prior-week overall count')
    if text.count('?') > 1:
        errors.append('clarification response asks more than one question')

    count_spans = _count_spans(lower)
    if len(count_spans) != 1:
        errors.append('clarification response must contain exactly one governed prior-week overall count expression')

    self_action_spans, self_action_errors = _self_action_clauses(lower)
    errors.extend(self_action_errors)

    # Closed sentence grammar: after replacing owned count/self-action spans,
    # the entire remaining surface must be one of the governed request shapes.
    # NFKC normalization makes compatibility characters visible to that grammar;
    # non-Latin or otherwise unowned content cannot disappear during tokenization.
    surface = _owned_surface(lower, count_spans, self_action_spans)
    if not GOVERNED_SURFACE.fullmatch(surface):
        errors.append('clarification response requests more than the prior-week overall count: ungoverned request structure')

    if 'nipr' in lower and 'sipr' in lower and re.search(r'\bcounts\b', lower) and not re.search(r'\b(?:combined|overall)\b', lower):
        errors.append('clarification response requests more than the prior-week overall count: separate NIPR/SIPR counts')

    for forbidden in ('readiness', 'normalize', 'normalized', 'evidence set', 'source data received', 'query', 'reporting window', 'date range'):
        if forbidden in lower:
            errors.append(f'clarification response adds unrelated requirement: {forbidden}')
    return errors
