#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'project_sources/agent_runtime/tools/score_usb_reporting_behavior.py'
NIPR_FIXTURE = ROOT / 'project_sources/validation/fixtures/agent_runtime/usb_reporting/inputs/violations_sanitized_nipr.csv'
MIXED_FIXTURE = ROOT / 'project_sources/validation/fixtures/agent_runtime/usb_reporting/inputs/violations_sanitized_mixed.csv'

spec = importlib.util.spec_from_file_location('score_usb_reporting_behavior', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

START = '9/18/2026'
END = '9/24/2026'
PREVIOUS = 6


def _date_text(raw: str) -> str:
    date, rest = raw.strip().split(maxsplit=1)
    month, day, year = [int(x) for x in date.split('/')]
    rest = rest.strip().replace(':', '')
    return f'{month:02d}/{day:02d}/{year:04d} {rest}'


def _incident(row: dict[str, str]) -> str:
    value = module._value
    lines = [
        f"Date: {_date_text(value(row, 'Date'))}",
        f"Name(s): {value(row, 'User')}",
        f"Location: {value(row, 'Location')}",
        f"Computer Name: {value(row, 'Computer Name')}",
        f"User Information: {value(row, 'User Information')}",
        f"USB Device: {value(row, 'USB Device')}",
        f"Serial Number: {value(row, 'Serial Number')}",
        f"Network Connection: {value(row, 'Network connection')}",
    ]
    notes = value(row, 'Notes')
    if notes:
        lines.append(f'Notes: {notes}')
    lines.append(value(row, 'SNOW Ticket Number'))
    return '\n'.join(lines)


def _body(rows: list[dict[str, str]], opening: str) -> str:
    return opening + '\n\n' + '\n\n'.join(_incident(row) for row in rows) + '\n\nPlease let us know if there are any questions.'


def _nipr_response(rows: list[dict[str, str]]) -> str:
    opening, _ = module._expected_openings(len(rows), 0, PREVIOUS, START, END)
    return f'''Recipient:\n```text\n{module.NIPR_RECIPIENT}\n```\n\nSubject:\n```text\n{module._subject(START, END)}\n```\n\nMessage Draft:\n```text\n{_body(rows, opening)}\n```'''


def _mixed_response(rows: list[dict[str, str]]) -> str:
    nipr = [row for row in rows if module._classification(row) == 'NIPR']
    sipr = [row for row in rows if module._classification(row) == 'SIPR']
    nipr_open, sipr_open = module._expected_openings(len(nipr), len(sipr), PREVIOUS, START, END)
    return f'''NIPR Recipient:\n```text\n{module.NIPR_RECIPIENT}\n```\n\nNIPR Subject:\n```text\n{module._subject(START, END)}\n```\n\nNIPR Message Draft:\n```text\n{_body(nipr, nipr_open)}\n```\n\nSIPR Recipient:\n```text\n{module.SIPR_RECIPIENT}\n```\n\nSIPR Subject:\n```text\n{module._subject(START, END)}\n```\n\nSIPR Message Draft:\n```text\n{_body(sipr, sipr_open or '')}\n```\n\nSIPR Transfer Instructions:\nCopy the SIPR recipient, SIPR subject, and SIPR message draft into a text document and move that text document to SIPR using Intelink iSafe: {module.ISAFE_URL}'''


def test_positive_nipr_email_construction() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    result = module.score_final_response(_nipr_response(rows), rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert result['passed'], result
    assert result['nipr_count'] == 7 and result['sipr_count'] == 0


def test_positive_mixed_email_construction() -> None:
    rows = module.load_fixture_rows(MIXED_FIXTURE)
    result = module.score_final_response(_mixed_response(rows), rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert result['passed'], result
    assert result['nipr_count'] == 5 and result['sipr_count'] == 2


def test_marker_only_email_shape_is_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    fake = f'''Recipient:\n```text\n{module.NIPR_RECIPIENT}\n```\nSubject:\n```text\n{module._subject(START, END)}\n```\nMessage Draft:\n```text\nFor the week of {START} - {END} there were 7 reported USB violations. Last week there were 6. See below for details.\nDate: [Date] [Time]Z\nName(s): [User]\nLocation: [Location]\nPlease let us know if there are any questions.\n```'''
    result = module.score_final_response(fake, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('INCNDUMMY0001' in error or 'incident count mismatch' in error for error in result['errors'])


def test_bluf_scaffolding_is_rejected_even_with_valid_email() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = 'BLUF:\nThe dataset is ready.\n\n' + _nipr_response(rows)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('BLUF' in error for error in result['errors'])


def test_mixed_classification_leakage_is_rejected() -> None:
    rows = module.load_fixture_rows(MIXED_FIXTURE)
    response = _mixed_response(rows)
    response = response.replace('Please let us know if there are any questions.\n```\n\nSIPR Recipient:', 'INCSDUMMY0006\nPlease let us know if there are any questions.\n```\n\nSIPR Recipient:', 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('opposite-classification' in error for error in result['errors'])


def test_missing_real_row_is_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows).replace('\n\n' + _incident(rows[-1]), '')
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('INCNDUMMY0007' in error or 'incident count mismatch' in error for error in result['errors'])



def test_missing_date_line_is_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows)
    expected_date = module._expected_date_line(rows[0])
    assert expected_date
    response = response.replace(expected_date + '\n', '', 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('missing source date/time' in error for error in result['errors'])


def test_nonblank_notes_are_required() -> None:
    rows = [dict(row) for row in module.load_fixture_rows(NIPR_FIXTURE)]
    rows[0]['notes'] = 'Operator-provided note'
    response = _nipr_response(rows)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert result['passed'], result
    response = response.replace('Notes: Operator-provided note\n', '', 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('missing Notes' in error for error in result['errors'])


def test_out_of_order_incidents_are_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows)
    first = _incident(rows[0])
    second = _incident(rows[1])
    response = response.replace(first + '\n\n' + second, second + '\n\n' + first, 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('incident order' in error for error in result['errors'])



def test_swapped_same_lane_fields_are_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows)
    response = response.replace('Name(s): Dummy User 01', 'Name(s): __SWAP__', 1)
    response = response.replace('Name(s): Dummy User 02', 'Name(s): Dummy User 01', 1)
    response = response.replace('Name(s): __SWAP__', 'Name(s): Dummy User 02', 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('INCNDUMMY0001' in error and 'Name(s)' in error for error in result['errors'])


def test_unbound_invented_incident_data_is_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows)
    invented = '''Date: 09/24/2026 0300Z
Name(s): Invented User
Location: Invented Location
Computer Name: INVENTED-PC
User Information: Invented User Information
USB Device: Invented Device
Serial Number: INVENTED-SERIAL
Network Connection: On-Site
INCNDUMMY9999'''
    response = response.replace(
        '\n\nPlease let us know if there are any questions.',
        '\n\n' + invented + '\n\nPlease let us know if there are any questions.',
        1,
    )
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('unexpected/unbound ticket: INCNDUMMY9999' in error for error in result['errors'])

def test_usb_device_brand_capitalization_is_allowed() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows)
    response = response.replace(
        'USB Device: NetGear, Inc. Remote NDIS Compatible Device',
        'USB Device: NETGEAR, Inc. Remote NDIS Compatible Device',
        1,
    )
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert result['passed'], result


def test_inline_sipr_transfer_label_is_rejected() -> None:
    rows = module.load_fixture_rows(MIXED_FIXTURE)
    response = _mixed_response(rows)
    response = response.replace(
        'SIPR Transfer Instructions:\nCopy the SIPR recipient',
        'SIPR Transfer Instructions: Copy the SIPR recipient',
        1,
    )
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('SIPR Transfer Instructions label' in error for error in result['errors'])

def test_wrong_recipient_is_rejected() -> None:
    rows = module.load_fixture_rows(NIPR_FIXTURE)
    response = _nipr_response(rows).replace(module.NIPR_RECIPIENT, 'wrong@example.mil', 1)
    result = module.score_final_response(response, rows, start_date=START, end_date=END, previous_count=PREVIOUS)
    assert not result['passed'], result
    assert any('governed NIPR address' in error for error in result['errors'])


def test_bounded_prior_count_clarification_passes() -> None:
    result = module.score_clarification_response("What was last week's single overall USB violation count?")
    assert result['passed'], result


def test_generic_bluf_clarification_fails() -> None:
    result = module.score_clarification_response("BLUF: I need last week's count before I can assess readiness.")
    assert not result['passed'], result
    assert any('BLUF' in error for error in result['errors'])



def test_extra_clarification_question_is_rejected() -> None:
    result = module.score_clarification_response(
        "What was last week's single overall USB violation count? Also confirm the reporting window?"
    )
    assert not result['passed'], result
    assert any('more than one question' in error or 'reporting window' in error for error in result['errors'])

def main() -> int:
    tests = [
        test_positive_nipr_email_construction,
        test_positive_mixed_email_construction,
        test_marker_only_email_shape_is_rejected,
        test_bluf_scaffolding_is_rejected_even_with_valid_email,
        test_mixed_classification_leakage_is_rejected,
        test_missing_real_row_is_rejected,
        test_missing_date_line_is_rejected,
        test_nonblank_notes_are_required,
        test_out_of_order_incidents_are_rejected,
        test_swapped_same_lane_fields_are_rejected,
        test_unbound_invented_incident_data_is_rejected,
        test_usb_device_brand_capitalization_is_allowed,
        test_inline_sipr_transfer_label_is_rejected,
        test_wrong_recipient_is_rejected,
        test_bounded_prior_count_clarification_passes,
        test_generic_bluf_clarification_fails,
        test_extra_clarification_question_is_rejected,
    ]
    for test in tests:
        test()
    print({'success': True, 'tests': [test.__name__ for test in tests]})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
