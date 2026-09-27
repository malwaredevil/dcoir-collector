#!/usr/bin/env python3
"""Response-wide incident/field evidence grammar for governed USB report output."""
from __future__ import annotations

import re

FINAL_LABELS = {
    'Recipient', 'Subject', 'Message Draft',
    'NIPR Recipient', 'NIPR Subject', 'NIPR Message Draft',
    'SIPR Recipient', 'SIPR Subject', 'SIPR Message Draft',
    'SIPR Transfer Instructions',
}
INCIDENT_LABELS = (
    'Date',
    'Name(s)',
    'Location',
    'Computer Name',
    'User Information',
    'USB Device',
    'Serial Number',
    'Network Connection',
    'Notes',
)
# Governed Field / Current Value / Suggested Value source-correction labels and
# correction leads are the only field-like lines permitted outside the drafts.
CORRECTION_LABELS = frozenset({'field', 'current value', 'suggested value'})
CLOSING = 'Please let us know if there are any questions.'
FIELD_LIKE = re.compile(r'^([A-Za-z][A-Za-z0-9 ()/_-]{0,63}):(.*)$')
LABEL_CONNECTORS = frozenset({'a', 'an', 'and', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'per', 'the', 'to', 'with'})
TICKET_LINE = re.compile(r'(?:INCN|INCS)\S*', flags=re.IGNORECASE)

def strip_presentation(text: str) -> str:
    """Remove Markdown/HTML/link presentation wrappers around a candidate evidence line."""
    text = re.sub(r'</?[A-Za-z][^>]*>', '', text)
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^(?:(?:>\s*)|(?:[-*+]\s+)|(?:\d+[.)]\s+)|(?:#{1,6}\s+))+', '', text)
    return text.strip('`*_~')


def incident_shape_errors(block: str, lane: str, ticket: str) -> list[str]:
    errors: list[str] = []
    order: list[int] = []
    for line in block.splitlines():
        candidate = line.lstrip(' \t')
        presented = strip_presentation(candidate)
        known_label = next((label for label in INCIDENT_LABELS if presented.startswith(f'{label}:')), None)
        if known_label is not None:
            order.append(INCIDENT_LABELS.index(known_label))
            if candidate != line or presented != candidate:
                errors.append(f'{lane} body contains noncanonical incident label for ticket {ticket}: {candidate}')
            continue
        if FIELD_LIKE.match(presented):
            errors.append(f'{lane} body contains unknown/noncanonical incident label for ticket {ticket}: {candidate}')
        elif (candidate != line or presented != candidate) and TICKET_LINE.fullmatch(presented):
            errors.append(f'{lane} body contains noncanonical ticket line for ticket {ticket}: {candidate}')
    if order != sorted(order):
        errors.append(f'{lane} body incident field order is noncanonical for ticket {ticket}')
    return errors


def presentation_wrapped_incident_evidence(text: str) -> list[str]:
    errors: list[str] = []
    labels = tuple(f'{label}:'.casefold() for label in INCIDENT_LABELS)
    for line in text.splitlines():
        candidate = line.lstrip(' \t')
        stripped = strip_presentation(candidate)
        if stripped == candidate:
            continue
        if _is_correction_line(stripped):
            continue
        if TICKET_LINE.fullmatch(stripped) or stripped.casefold().startswith(labels) or FIELD_LIKE.match(stripped):
            errors.append(f'final response contains Markdown-prefixed incident evidence: {candidate}')
    return errors


def _is_correction_line(stripped: str) -> bool:
    """A governed Field / Current Value / Suggested Value source-correction line."""
    match = FIELD_LIKE.match(stripped)
    return bool(match) and match.group(1).strip().casefold() in CORRECTION_LABELS


def unexpected_prose_errors(
    prose: str, correction_source_values: dict[str, set[str]] | None = None,
) -> list[str]:
    """Outside drafts, permit only complete source-backed correction records."""
    errors: list[str] = []
    lines = [strip_presentation(line.strip()) for line in prose.splitlines() if strip_presentation(line.strip())]
    source_values = correction_source_values or {}
    index = 0
    while index < len(lines):
        if index + 2 >= len(lines):
            errors.append(f'final response contains prose outside the governed drafts: {lines[index]}')
            break
        parsed = [FIELD_LIKE.match(lines[index + offset]) for offset in range(3)]
        labels = [item.group(1).strip().casefold() if item else '' for item in parsed]
        if labels != ['field', 'current value', 'suggested value']:
            errors.append(f'final response contains prose outside the governed drafts: {lines[index]}')
            index += 1
            continue
        field = parsed[0].group(2).strip()
        current = parsed[1].group(2).strip()
        suggested = parsed[2].group(2).strip()
        if not field or not current or not suggested:
            errors.append('final response contains incomplete source correction values')
        allowed_current = source_values.get(field.casefold())
        if allowed_current is None:
            errors.append(f'final response source correction uses unknown field: {field}')
        elif current not in allowed_current:
            errors.append(f'final response source correction current value is not source-backed: {field}: {current}')
        index += 3
    return errors


def body_line_errors(body: str, lane: str, opening: str | None) -> list[str]:
    """Every non-blank draft body line must be the opening, an incident line, or the closing."""
    labels = tuple(f'{label}:' for label in INCIDENT_LABELS)
    allowed = {CLOSING} | ({opening} if opening else set())
    return [
        f'{lane} body contains free prose outside the governed template: {line.strip()}'
        for line in body.splitlines()
        if line.strip() and line.strip() not in allowed
        and not line.lstrip(' \t').startswith(labels) and not TICKET_LINE.fullmatch(line.strip())
    ]


def _is_label_shaped(label: str) -> bool:
    """Short leads are always labels; longer ones only when Title/UPPER case like a form field.

    A long lead with ordinary lowercase words ("Move it to SIPR using Intelink iSafe") is prose.
    """
    words = label.split()
    if len(words) <= 4:
        return True
    return all(word[0].isupper() or word[0].isdigit() or word in LABEL_CONNECTORS for word in words)


def unbound_field_like_evidence(text: str) -> list[str]:
    """Reject field-like lines outside every fenced governed draft.

    Governed label lines and source-correction labels are allowed; incident labels
    are counted separately. Anything else is invented field/disposition evidence.
    """
    outside = re.sub(r'(?ms)^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*$', '', text)
    incident = {label.casefold() for label in INCIDENT_LABELS}
    governed = {label.casefold() for label in FINAL_LABELS}
    errors: list[str] = []
    for line in outside.splitlines():
        match = FIELD_LIKE.match(strip_presentation(line.strip()))
        if not match:
            continue
        raw_label = match.group(1).strip()
        label = raw_label.casefold()
        if not _is_label_shaped(raw_label) or label in incident or label in CORRECTION_LABELS:
            continue
        if label in governed and not match.group(2).strip():
            continue
        errors.append(f'final response contains field-like evidence outside the governed drafts: {line.strip()}')
    return errors
