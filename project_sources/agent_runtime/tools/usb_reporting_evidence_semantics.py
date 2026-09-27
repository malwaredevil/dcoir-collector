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
CORRECTION_LABELS = frozenset({
    'field', 'current value', 'suggested value',
    'correction', 'correction needed', 'source correction', 'source correction needed',
})
FIELD_LIKE = re.compile(r'^([A-Za-z][A-Za-z0-9 ()/_-]{0,63}):(.*)$')
TICKET_LINE = re.compile(r'(?:INCN|INCS)\S*', flags=re.IGNORECASE)


def strip_presentation(text: str) -> str:
    """Remove Markdown/HTML/link presentation wrappers around a candidate evidence line."""
    text = re.sub(r'</?[A-Za-z][^>]*>', '', text)
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^(?:(?:>\s*)|(?:[-*+]\s+)|(?:\d+[.)]\s+)|(?:#{1,6}\s+))+', '', text)
    return text.strip('`*_~')


def incident_shape_errors(block: str, lane: str, ticket: str) -> list[str]:
    errors: list[str] = []
    for line in block.splitlines():
        candidate = line.lstrip(' \t')
        presented = strip_presentation(candidate)
        known_label = next((label for label in INCIDENT_LABELS if presented.startswith(f'{label}:')), None)
        if known_label is not None:
            if candidate != line or presented != candidate:
                errors.append(f'{lane} body contains noncanonical incident label for ticket {ticket}: {candidate}')
            continue
        if FIELD_LIKE.match(presented):
            errors.append(f'{lane} body contains unknown/noncanonical incident label for ticket {ticket}: {candidate}')
        elif (candidate != line or presented != candidate) and TICKET_LINE.fullmatch(presented):
            errors.append(f'{lane} body contains noncanonical ticket line for ticket {ticket}: {candidate}')
    return errors


def presentation_wrapped_incident_evidence(text: str) -> list[str]:
    errors: list[str] = []
    labels = tuple(f'{label}:'.casefold() for label in INCIDENT_LABELS)
    for line in text.splitlines():
        candidate = line.lstrip(' \t')
        stripped = strip_presentation(candidate)
        if stripped == candidate:
            continue
        if TICKET_LINE.fullmatch(stripped) or stripped.casefold().startswith(labels) or FIELD_LIKE.match(stripped):
            errors.append(f'final response contains Markdown-prefixed incident evidence: {candidate}')
    return errors


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
        label = match.group(1).strip().casefold()
        # Longer lead-ins are prose sentences (for example a split transfer line), not field labels.
        if len(label.split()) > 4 or label in incident or label in CORRECTION_LABELS:
            continue
        if label in governed and not match.group(2).strip():
            continue
        errors.append(f'final response contains field-like evidence outside the governed drafts: {line.strip()}')
    return errors
