#!/usr/bin/env python3
"""Response-wide incident/field evidence regressions for the USB report scorer."""
from __future__ import annotations

INVENTED_INCIDENT = [
    'Date: 09/24/2026 0300Z',
    'Name(s): Invented User',
    'Location: Invented Location',
    'Computer Name: INVENTED-PC',
    'User Information: Invented User Information',
    'USB Device: Invented Device',
    'Serial Number: INVENTED-SERIAL',
    'Network Connection: On-Site',
]


def run_evidence_tests(module, nipr_fixture, nipr_response, start, end, previous):
    rows = module.load_fixture_rows(nipr_fixture)
    first_ticket = module._value(rows[0], 'SNOW Ticket Number')
    last_ticket = module._value(rows[-1], 'SNOW Ticket Number')

    def score(response):
        return module.score_final_response(
            response, rows, start_date=start, end_date=end, previous_count=previous,
        )

    def assert_rejected(response, *needles):
        result = score(response)
        assert not result['passed'], (response[-160:], result)
        assert any(needle in error for error in result['errors'] for needle in needles), result

    base = nipr_response(rows)

    # Indented duplicate incident fields inside the governed draft.
    first_date = module._expected_date_line(rows[0])
    assert first_date
    assert_rejected(base.replace(first_date, first_date + '\n Date: 01/01/1999 0000Z', 1),
                    'noncanonical incident label', 'Date evidence count mismatch')
    location = f"Location: {module._value(rows[0], 'Location')}"
    assert_rejected(base.replace(location, location + '\n Location: WRONG', 1),
                    'noncanonical incident label', 'Location evidence count mismatch')
    assert_rejected(base.replace(first_ticket, ' Notes: Invented exculpatory note\n' + first_ticket, 1),
                    'noncanonical incident label', 'Notes evidence count mismatch')

    # Unknown field-like labels inside the governed draft.
    assert_rejected(base.replace(location, location + '\nApproval Status: Cleared', 1),
                    'unknown/noncanonical incident label')
    for label in ('Approval Status: Cleared', 'Analyst Finding: No policy violation', 'Disposition: Authorized device'):
        assert_rejected(base.replace(last_ticket + '\n\nPlease', last_ticket + '\n' + label + '\n\nPlease', 1),
                        'unknown/noncanonical incident label')

    # A complete invented incident after the final fence.
    assert_rejected(base + '\n\n' + '\n'.join(INVENTED_INCIDENT + ['INCNDUMMY9999']),
                    'incident ticket evidence outside the governed drafts', 'Name(s) evidence count mismatch')

    # Presentation-wrapped incident evidence anywhere in the response.
    for prefix in ('> ', '- '):
        fake = ['INCNDUMMY9999'] + INVENTED_INCIDENT
        assert_rejected(base + '\n\n' + '\n'.join(prefix + line for line in fake),
                        'Markdown-prefixed incident evidence')
    for evidence in (
        '> date: 01/01/1999 0000Z', '- notes: Invented exculpatory evidence', '> LoCaTiOn: WRONG',
        '**Date:** 01/01/1999 0000Z', '`Date:` 01/01/1999 0000Z', '# Date: 01/01/1999 0000Z',
        '> **Date:** 01/01/1999 0000Z', '**Approval Status:** Cleared', '`Disposition:` Authorized device',
        '<b>Date:</b> 01/01/1999 0000Z', '[Notes](https://example.invalid): Invented note',
    ):
        assert_rejected(base + '\n\n' + evidence, 'Markdown-prefixed incident evidence')

    # Plain, link-wrapped, and HTML-wrapped invented labels after the final fence.
    for evidence in (
        'Approval Status: Cleared', 'Analyst Finding: No policy violation', 'Disposition: Authorized device',
        '[Approval Status](https://example.invalid): Cleared', '<b>Approval Status:</b> Cleared',
        '<strong>Analyst Finding</strong>: No policy violation',
        'Command Security Final Disposition Status: Cleared',
        'Reviewed By Command Security Office: Approved',
    ):
        assert_rejected(base + '\n\n' + evidence,
                        'field-like evidence outside the governed drafts', 'Markdown-prefixed incident evidence')

    # Governed incident-field order is fixed within each ticket block.
    loc = f"Location: {module._value(rows[0], 'Location')}"
    host = f"Computer Name: {module._value(rows[0], 'Computer Name')}"
    assert_rejected(base.replace(loc + '\n' + host, host + '\n' + loc, 1), 'field order')

    # Blank source identity fields may remain blank but cannot be invented.
    blank_rows = [dict(row) for row in rows]
    blank_rows[0][module._norm_header('User')] = ''
    blank_base = nipr_response(blank_rows)
    blank_ok = module.score_final_response(blank_base, blank_rows, start_date=start, end_date=end, previous_count=previous)
    assert blank_ok['passed'], blank_ok
    invented = blank_base.replace('Name(s): \n', 'Name(s): Invented User\n', 1)
    invented_result = module.score_final_response(invented, blank_rows, start_date=start, end_date=end, previous_count=previous)
    assert not invented_result['passed'], invented_result
    assert any('invents Name(s)' in error for error in invented_result['errors']), invented_result

    # The clarification gate accepts natural ways to request one prior-week overall count.
    for text in (
        'How many USB violations were reported last week?',
        'What was the total number of USB violations last week?',
        "What was last week's overall USB violation count (NIPR and SIPR combined)?",
        "What was last week's overall USB violation count? I'll draft the report once I have it.",
        "What was last week's overall USB violation count?".replace(' ', '\u00a0', 1),
    ):
        result = module.score_clarification_response(text)
        assert result['passed'], (text, result)
    broad = module.score_clarification_response('Please send us all of the USB violation reports for last week so we can count.')
    assert not broad['passed'], broad

    # Governed Field / Current Value / Suggested Value correction notes remain allowed.
    correction = (
        '\n\nCorrection needed: confirm the Network Connection before sending.\n'
        'Field: Network Connection\nCurrent Value: onsite\nSuggested Value: On-Site'
    )
    result = score(base + correction)
    assert result['passed'], result
    # A long prose lead-in ending in a colon is not a field label.
    prose = '\n\nPlease confirm the Network Connection value for the first row: the source cell is ambiguous.'
    result = score(base + prose)
    assert result['passed'], result

    return [
        'indented_duplicate_incident_fields',
        'unknown_incident_labels_in_draft',
        'invented_incident_after_message_fence',
        'presentation_wrapped_incident_evidence',
        'unbound_field_like_evidence_after_fence',
        'governed_field_order_and_blank_identity',
        'bounded_clarification_natural_phrasings',
        'governed_source_correction_note_allowed',
    ]
