#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

NIPR_RECIPIENT = 'africom.stuttgart.acj6.list.africom-usb-violations@mail.mil'
SIPR_RECIPIENT = 'africom.stuttgart.acj6.list.africom-usb-violations@mail.smil.mil'
ISAFE_URL = 'https://isafe.intelink.gov/'
FORBIDDEN_SCAFFOLD = {
    'BLUF',
    'EVIDENCE NEED',
    'SOURCE DATA RECEIVED',
    'NORMALIZED USB EVENTS',
    'REPORTING IMPLICATIONS',
    'GAPS OR ASSUMPTIONS',
    'NEXT CONFIRMATION',
    'RECOMMENDATIONS',
}
FINAL_LABELS = {
    'Recipient', 'Subject', 'Message Draft',
    'NIPR Recipient', 'NIPR Subject', 'NIPR Message Draft',
    'SIPR Recipient', 'SIPR Subject', 'SIPR Message Draft',
    'SIPR Transfer Instructions',
}


def _norm_header(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def load_fixture_rows(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {_norm_header(str(k or '')): str(v or '').strip() for k, v in raw.items()}
            if any(row.values()):
                rows.append(row)
    return rows


def _value(row: dict[str, str], name: str) -> str:
    return row.get(_norm_header(name), '').strip()


def _ticket(row: dict[str, str]) -> str:
    return _value(row, 'SNOW Ticket Number')


def _classification(row: dict[str, str]) -> str:
    ticket = _ticket(row).upper()
    if ticket.startswith('INCN'):
        return 'NIPR'
    if ticket.startswith('INCS'):
        return 'SIPR'
    return 'UNKNOWN'


def _forbidden_scaffold_errors(text: str) -> list[str]:
    errors: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        for heading in FORBIDDEN_SCAFFOLD:
            if re.match(rf'^{re.escape(heading)}(?:\s*:|\s*$)', stripped, flags=re.IGNORECASE):
                errors.append(f'forbidden generic scaffold heading: {heading}')
                break
    return errors


def _label_matches(text: str, label: str) -> list[re.Match[str]]:
    return list(re.finditer(rf'(?m)^{re.escape(label)}:\s*$', text))


def _extract_fenced_value(text: str, label: str) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    matches = _label_matches(text, label)
    if len(matches) != 1:
        return None, [f'expected exactly one {label}: label, found {len(matches)}']
    rest = text[matches[0].end():]
    start = re.match(r'\s*\n```[^\n]*\n', rest)
    if not start:
        return None, [f'{label}: is not followed by one fenced block']
    body_start = start.end()
    end = rest.find('\n```', body_start)
    if end < 0:
        return None, [f'{label}: fenced block is not closed']
    return rest[body_start:end].strip('\n'), errors


def _expected_date_line(row: dict[str, str]) -> str | None:
    raw = _value(row, 'Date') or _value(row, 'Date w/Time in Z')
    match = re.match(r'^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(.+?)\s*$', raw)
    if not match:
        return None
    month, day, year, time_text = match.groups()
    time_text = re.sub(r'(?<=\d):(?=\d)', '', time_text)
    return f'Date: {int(month):02d}/{int(day):02d}/{int(year):04d} {time_text}'


def _count_phrase(count: int, noun: str = 'USB violation') -> str:
    verb = 'was' if count == 1 else 'were'
    suffix = '' if count == 1 else 's'
    return f'there {verb} {count} {noun}{suffix}'


def _subject(start_date: str, end_date: str) -> str:
    return f'Weekly USB Violations {start_date} - {end_date}'


def _expected_openings(nipr_count: int, sipr_count: int, previous_count: int, start_date: str, end_date: str) -> tuple[str, str | None]:
    prev_verb = 'was' if previous_count == 1 else 'were'
    if sipr_count == 0:
        verb = 'was' if nipr_count == 1 else 'were'
        noun = 'violation' if nipr_count == 1 else 'violations'
        return (
            f'For the week of {start_date} - {end_date} there {verb} {nipr_count} reported USB {noun}. '
            f'Last week there {prev_verb} {previous_count}. See below for details.',
            None,
        )
    nipr_noun = 'violation' if nipr_count == 1 else 'violations'
    sipr_noun = 'violation' if sipr_count == 1 else 'violations'
    referent = 'that one' if sipr_count == 1 else 'those'
    nipr_open = (
        f'For the week of {start_date} - {end_date} there were {nipr_count} NIPR USB {nipr_noun} '
        f'and {sipr_count} SIPR USB {sipr_noun}. Last week there {prev_verb} {previous_count}. '
        f'Details can be found below for the NIPR USB violations, please check SIPR for the details on {referent}.'
    )
    sipr_verb = 'was' if sipr_count == 1 else 'were'
    sipr_open = (
        f'For the week of {start_date} - {end_date} there {sipr_verb} {sipr_count} SIPR USB {sipr_noun}. '
        'See below for details.'
    )
    return nipr_open, sipr_open


def _row_errors(body: str, rows: list[dict[str, str]], lane: str) -> list[str]:
    errors: list[str] = []
    expected = [row for row in rows if _classification(row) == lane]
    forbidden = [row for row in rows if _classification(row) not in {lane, 'UNKNOWN'}]
    if body.count('Name(s):') != len(expected):
        errors.append(f'{lane} body incident count mismatch: expected {len(expected)}, saw {body.count("Name(s):")}')
    required_fields = [
        ('Name(s)', 'User'),
        ('Location', 'Location'),
        ('Computer Name', 'Computer Name'),
        ('User Information', 'User Information'),
        ('USB Device', 'USB Device'),
        ('Serial Number', 'Serial Number'),
        ('Network Connection', 'Network connection'),
    ]
    ticket_positions: list[int] = []
    for row in expected:
        ticket = _ticket(row)
        ticket_matches = list(re.finditer(rf'(?m)^{re.escape(ticket)}\s*$', body))
        if len(ticket_matches) != 1:
            errors.append(f'{lane} body must contain ticket exactly once: {ticket}')
        else:
            ticket_positions.append(ticket_matches[0].start())
        expected_date = _expected_date_line(row)
        if expected_date is None:
            errors.append(f'{lane} fixture date is not parseable for ticket: {ticket}')
        elif expected_date not in body:
            errors.append(f'{lane} body missing source date/time: {expected_date}')
        for label, field in required_fields:
            value = _value(row, field)
            if value and f'{label}: {value}' not in body:
                errors.append(f'{lane} body missing source value {label}: {value}')
        notes = _value(row, 'Notes')
        if notes and f'Notes: {notes}' not in body:
            errors.append(f'{lane} body missing Notes: {notes}')
    if len(ticket_positions) == len(expected) and ticket_positions != sorted(ticket_positions):
        errors.append(f'{lane} body incident order does not match ascending fixture order')
    if expected and not any(_value(row, 'Notes') for row in expected) and re.search(r'(?m)^Notes:', body):
        errors.append(f'{lane} body must omit blank Notes lines')
    for row in forbidden:
        ticket = _ticket(row)
        if ticket and ticket in body:
            errors.append(f'{lane} body leaks opposite-classification ticket: {ticket}')
    if not body.rstrip().endswith('Please let us know if there are any questions.'):
        errors.append(f'{lane} body does not use the exact governed closing')
    return errors


def score_final_response(
    text: str,
    rows: list[dict[str, str]],
    *,
    start_date: str,
    end_date: str,
    previous_count: int,
) -> dict[str, Any]:
    errors = _forbidden_scaffold_errors(text)
    unknown = [_ticket(row) for row in rows if _classification(row) == 'UNKNOWN']
    if unknown:
        errors.append('fixture contains unknown ticket prefix: ' + ', '.join(unknown))
    nipr = [row for row in rows if _classification(row) == 'NIPR']
    sipr = [row for row in rows if _classification(row) == 'SIPR']
    mixed = bool(sipr)
    expected_first = 'NIPR Recipient:' if mixed else 'Recipient:'
    first = next((line.strip() for line in text.splitlines() if line.strip()), '')
    if first != expected_first:
        errors.append(f'final response must start with {expected_first}, got {first!r}')
    subject = _subject(start_date, end_date)
    if mixed:
        labels = ['NIPR Recipient', 'NIPR Subject', 'NIPR Message Draft', 'SIPR Recipient', 'SIPR Subject', 'SIPR Message Draft']
        values: dict[str, str] = {}
        for label in labels:
            value, block_errors = _extract_fenced_value(text, label)
            errors.extend(block_errors)
            if value is not None:
                values[label] = value
        if values.get('NIPR Recipient') != NIPR_RECIPIENT:
            errors.append('NIPR recipient is not the governed address')
        if values.get('SIPR Recipient') != SIPR_RECIPIENT:
            errors.append('SIPR recipient is not the governed address')
        if values.get('NIPR Subject') != subject or values.get('SIPR Subject') != subject:
            errors.append('mixed report subject does not match the governed reporting window')
        nipr_body = values.get('NIPR Message Draft', '')
        sipr_body = values.get('SIPR Message Draft', '')
        nipr_open, sipr_open = _expected_openings(len(nipr), len(sipr), previous_count, start_date, end_date)
        if nipr_open not in nipr_body:
            errors.append('NIPR body missing exact governed mixed opening/counts')
        if sipr_open and sipr_open not in sipr_body:
            errors.append('SIPR body missing exact governed opening/counts')
        errors.extend(_row_errors(nipr_body, rows, 'NIPR'))
        errors.extend(_row_errors(sipr_body, rows, 'SIPR'))
        transfer_matches = _label_matches(text, 'SIPR Transfer Instructions')
        if len(transfer_matches) != 1:
            errors.append(f'expected exactly one SIPR Transfer Instructions label, found {len(transfer_matches)}')
        else:
            transfer = text[transfer_matches[0].end():]
            if ISAFE_URL not in transfer or 'text document' not in transfer.lower():
                errors.append('SIPR transfer instructions lack text-document iSafe handling')
    else:
        values: dict[str, str] = {}
        for label in ['Recipient', 'Subject', 'Message Draft']:
            value, block_errors = _extract_fenced_value(text, label)
            errors.extend(block_errors)
            if value is not None:
                values[label] = value
        if values.get('Recipient') != NIPR_RECIPIENT:
            errors.append('recipient is not the governed NIPR address')
        if values.get('Subject') != subject:
            errors.append('subject does not match the governed reporting window')
        body = values.get('Message Draft', '')
        opening, _ = _expected_openings(len(nipr), 0, previous_count, start_date, end_date)
        if opening not in body:
            errors.append('message body missing exact governed opening/counts')
        errors.extend(_row_errors(body, rows, 'NIPR'))
        for label in ['NIPR Recipient', 'SIPR Recipient', 'SIPR Message Draft', 'SIPR Transfer Instructions']:
            if _label_matches(text, label):
                errors.append(f'NIPR-only response unexpectedly includes {label}:')
    return {
        'passed': not errors,
        'errors': errors,
        'row_count': len(rows),
        'nipr_count': len(nipr),
        'sipr_count': len(sipr),
        'semantic_contract': 'usb_reporting_email_construction_v1',
    }


def score_clarification_response(text: str) -> dict[str, Any]:
    errors = _forbidden_scaffold_errors(text)
    for label in FINAL_LABELS:
        if _label_matches(text, label):
            errors.append(f'clarification response prematurely emits final label {label}:')
    lower = text.lower()
    prior = ('last week' in lower or 'previous week' in lower) and 'count' in lower
    if not prior:
        errors.append('clarification response does not request the missing prior-week overall count')
    if text.count('?') > 1:
        errors.append('clarification response asks more than one question')
    for forbidden in ('readiness', 'normalize', 'normalized', 'evidence set', 'source data received', 'query', 'reporting window', 'date range'):
        if forbidden in lower:
            errors.append(f'clarification response adds unrelated requirement: {forbidden}')
    return {
        'passed': not errors,
        'errors': errors,
        'semantic_contract': 'usb_reporting_bounded_clarification_v1',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Semantically score governed USB reporting output.')
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--response', required=True)
    parser.add_argument('--mode', choices=['final', 'clarification'], required=True)
    parser.add_argument('--start-date', default='9/18/2026')
    parser.add_argument('--end-date', default='9/24/2026')
    parser.add_argument('--previous-week-count', type=int, default=6)
    args = parser.parse_args()
    text = Path(args.response).read_text(encoding='utf-8')
    if args.mode == 'clarification':
        result = score_clarification_response(text)
    else:
        rows = load_fixture_rows(Path(args.fixture))
        result = score_final_response(text, rows, start_date=args.start_date, end_date=args.end_date, previous_count=args.previous_week_count)
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
