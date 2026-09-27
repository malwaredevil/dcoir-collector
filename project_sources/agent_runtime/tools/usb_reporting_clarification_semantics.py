#!/usr/bin/env python3
"""Closed-contract validation for bounded USB prior-count clarification output."""
from __future__ import annotations

import re

COUNT_REFERENCE = re.compile(
    r"\b(?:"
    r"how\s+many\s+(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?(?:(?:single|overall|combined|total)\s+){0,2}"
    r"(?:number|count|total)(?:\s+of)?\s+(?:all\s+)?(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?(?:all\s+)?(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?"
    r"usb\s+violations?\s+(?:(?:single|overall|combined|total)\s+){0,2}(?:number|count|total)"
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
REQUEST_FRAME_WORDS = frozenset("""
a are can combined could count counts did for from give how is know last let many me need number of overall
please previous prior provide reported share single tell the there to total us was week weekly were what with would you
""".split())



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


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _residual_words(text: str, owned_spans: list[tuple[int, int]]) -> list[str]:
    residual = text
    for start, end in reversed(_merge_spans(owned_spans)):
        residual = residual[:start] + (' ' * (end - start)) + residual[end:]
    residual = re.sub(r"(?<=\w)['’]s\b", '', residual)
    return re.findall(r'[a-z]+', residual)


def clarification_content_errors(text: str) -> list[str]:
    lower = re.sub(r'\s+', ' ', text.lower().replace('\u00a0', ' ')).strip()
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

    # Closed ownership rule: once the one governed count expression and any
    # validated benign self-action are removed, only neutral request framing may
    # remain. This rejects new record synonyms, punctuation tricks, and extra
    # operational demands without maintaining separate noun/verb blacklists.
    residual = _residual_words(lower, count_spans + self_action_spans)
    extra = sorted({word for word in residual if word not in REQUEST_FRAME_WORDS})
    if extra:
        errors.append('clarification response requests more than the prior-week overall count: unowned language: ' + ', '.join(extra))

    if 'nipr' in lower and 'sipr' in lower and re.search(r'\bcounts\b', lower) and not re.search(r'\b(?:combined|overall)\b', lower):
        errors.append('clarification response requests more than the prior-week overall count: separate NIPR/SIPR counts')

    for forbidden in ('readiness', 'normalize', 'normalized', 'evidence set', 'source data received', 'query', 'reporting window', 'date range'):
        if forbidden in lower:
            errors.append(f'clarification response adds unrelated requirement: {forbidden}')
    return errors
