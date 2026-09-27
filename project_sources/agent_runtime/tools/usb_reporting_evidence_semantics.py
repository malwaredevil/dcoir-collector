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

CLARIFICATION_DELIVERY = re.compile(r'\b(?:email|send|share|write|prepare|provide|give|compose|finalize|finish|draft)\b', re.I)
CLARIFICATION_RECORD_OBJECT = re.compile(
    r'\b(?:usb\s+violations?|violations?|all\s+(?:nipr|sipr)(?:\s+and\s+(?:nipr|sipr))?|violation\s+(?:records?|details?)|reports?|data|rows?|incidents?|records?|details?)\b', re.I,
)
CLARIFICATION_COUNT_SCOPE = re.compile(r'\b(?:counts?|number|total|overall|combined|how\s+many)\b', re.I)
CLARIFICATION_COUNT_REFERENCE = re.compile(
    r"\b(?:"
    r"how\s+many\s+(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?(?:(?:single|overall|combined|total)\s+){0,2}"
    r"(?:number|count|total)(?:\s+of)?\s+(?:all\s+)?(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?"
    r"|(?:(?:last|previous)\s+week(?:['’]s)?\s+)?(?:all\s+)?(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?"
    r"usb\s+violations?\s+(?:(?:single|overall|combined|total)\s+){0,2}(?:number|count|total)"
    r")\b",
    re.I,
)
CLARIFICATION_TRAILING_SELF_ACTION = re.compile(
    r"\b(?:i(?:['’]ll|\s+will|\s+can)|we(?:['’]ll|\s+will|\s+can)|"
    r"(?:before|after|once|so)\s+(?:i|we))\b",
    re.I,
)
CLARIFICATION_COUNT_OBJECT = re.compile(
    r'^\s*(?:me\s+|us\s+)?(?:the\s+)?(?:(?:last|previous)\s+week(?:[\'’]s)?\s+)?'
    r'(?:(?:single|overall|combined|total)\s+){0,2}(?:'
    r'(?:number|count|total)(?:\s+of)?\s+(?:all\s+)?(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?'
    r'|(?:(?:nipr\s+and\s+sipr|sipr\s+and\s+nipr)\s+)?usb\s+violations?\s+(?:number|count|total)'
    r')\b',
    re.I,
)
CLARIFICATION_SELF_ACTION = re.compile(
    r"(?:\b(?:before|after|once|so)\s+(?:i|we)|\bi(?:'ll|\s+will|\s+can)|"
    r"\bwe(?:'ll|\s+will|\s+can)|\blet\s+me)\s*$", re.I,
)
CLARIFICATION_SELF_CREATION = frozenset({'write', 'prepare', 'compose', 'finalize', 'finish', 'draft'})
CLARIFICATION_SELF_CREATION_OBJECT = re.compile(
    r'^\s*(?:me\s+|us\s+)?(?:the\s+|a\s+|this\s+|that\s+)?(?:report|draft|email)\b', re.I,
)
CLARIFICATION_SENSITIVE_RECORD_OBJECT = re.compile(
    r'\b(?:all\s+(?:nipr|sipr)|(?:nipr|sipr)(?:\s+and\s+(?:nipr|sipr))?\s+(?:usb\s+)?violations?'
    r'|usb\s+violations?|violation\s+(?:records?|details?)|data|rows?|incidents?|records?|details?)\b', re.I,
)
CLARIFICATION_SELF_TRANSMISSION = frozenset({'email', 'send', 'share', 'provide', 'give'})


CLARIFICATION_VOCABULARY = frozenset('''
a after all and are before can combined compose could complete count counts did draft drafts email emails final
finalize finish for from get give have how i in is it just know last let ll many me need nipr number of once overall please
prepare previous prior provide report reported reports send share single sipr so tell that the there this
to total us usb violation violations was we week weekly were what with would write you
'''.split())


def clarification_content_errors(text: str) -> list[str]:
    lower = text.lower().replace('\u00a0', ' ')
    errors: list[str] = []
    prior_week = bool(re.search(r"\b(?:last|previous)\s+week(?:'s)?\b", lower))
    quantity = bool(re.search(r'\b(?:counts?|number|total|overall|combined)\b|\bhow\s+many\b', lower))
    usb = bool(re.search(r'\busb\s+violations?\b', lower))
    if not (prior_week and quantity and usb):
        errors.append('clarification response does not request the missing prior-week overall count')
    if text.count('?') > 1:
        errors.append('clarification response asks more than one question')
    words = re.findall(r'[a-z]+', re.sub(r"['\u2019]s\b", '', lower))
    extra = sorted({word for word in words if word not in CLARIFICATION_VOCABULARY})
    if extra:
        errors.append('clarification response requests more than the prior-week overall count: ' + ', '.join(extra))
    if re.search(r'\b(?:send|provide|share|give)(?:\s+[a-z]+){0,7}\s+(?:reports?|data|rows?|incidents?)\b', lower):
        errors.append('clarification response requests more than the prior-week overall count: source reports/data')
    self_action = CLARIFICATION_TRAILING_SELF_ACTION.search(lower)
    request_scope = lower[:self_action.start()] if self_action else lower
    count_spans = [match.span() for match in CLARIFICATION_COUNT_REFERENCE.finditer(request_scope)]
    for record in CLARIFICATION_RECORD_OBJECT.finditer(request_scope):
        if any(start <= record.start() and record.end() <= end for start, end in count_spans):
            continue
        errors.append('clarification response requests more than the prior-week overall count: violation records')
        break
    if self_action:
        self_scope = lower[self_action.start():]
        self_count_spans = [match.span() for match in CLARIFICATION_COUNT_REFERENCE.finditer(self_scope)]
        for record in CLARIFICATION_SENSITIVE_RECORD_OBJECT.finditer(self_scope):
            if any(start <= record.start() and record.end() <= end for start, end in self_count_spans):
                continue
            errors.append('clarification response requests more than the prior-week overall count: self-action on violation records')
            break
    for action in CLARIFICATION_DELIVERY.finditer(lower):
        prefix = lower[max(0, action.start() - 24):action.start()]
        self_directed = bool(CLARIFICATION_SELF_ACTION.search(prefix))
        verb = action.group(0).lower()
        if verb == 'draft' and not self_directed and re.search(r'\b(?:the|a|this|that)\s*$', prefix):
            continue
        tail = lower[action.end():action.end() + 180]
        self_clause = re.search(r'\b(?:so|before|after|once)\s+(?:i|we)\b', tail)
        object_tail = tail[:self_clause.start()] if self_clause else tail
        record = CLARIFICATION_RECORD_OBJECT.search(object_tail)
        count_object = CLARIFICATION_COUNT_OBJECT.match(object_tail)
        extra_record = bool(count_object and CLARIFICATION_RECORD_OBJECT.search(object_tail[count_object.end():]))
        if self_directed and verb in CLARIFICATION_SELF_TRANSMISSION:
            if not count_object or extra_record:
                errors.append('clarification response requests more than the prior-week overall count: self-directed delivery or disclosure')
                break
            continue
        if self_directed and verb in CLARIFICATION_SELF_CREATION:
            creation_object = re.split(
                r'[,;!?]|\b(?:what|which|who|how|please|could|would|tell\s+me|let\s+me\s+know)\b',
                object_tail,
                maxsplit=1,
                flags=re.I,
            )[0]
            benign_creation = (
                CLARIFICATION_SELF_CREATION_OBJECT.match(creation_object)
                and not CLARIFICATION_SENSITIVE_RECORD_OBJECT.search(creation_object)
            )
            if benign_creation:
                continue
        if not record:
            continue
        if not count_object or extra_record:
            errors.append('clarification response requests more than the prior-week overall count: delivery or violation records')
            break
    if 'nipr' in lower and 'sipr' in lower and re.search(r'\bcounts\b', lower) and not re.search(r'\b(?:combined|overall)\b', lower):
        errors.append('clarification response requests more than the prior-week overall count: separate NIPR/SIPR counts')
    for forbidden in ('readiness', 'normalize', 'normalized', 'evidence set', 'source data received', 'query', 'reporting window', 'date range'):
        if forbidden in lower:
            errors.append(f'clarification response adds unrelated requirement: {forbidden}')
    return errors


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
