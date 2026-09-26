#!/usr/bin/env python3
from __future__ import annotations


def run_transfer_tests(module, mixed_fixture, mixed_response, start, end, previous):
    rows = module.load_fixture_rows(mixed_fixture)

    def score(response):
        return module.score_final_response(
            response,
            rows,
            start_date=start,
            end_date=end,
            previous_count=previous,
        )

    safe = (
        'Copy the SIPR recipient, SIPR subject, and SIPR message draft into a text document '
        f'and move that text document to SIPR using Intelink iSafe: {module.ISAFE_URL}'
    )
    unsafe_variants = [
        safe.replace(
            'and move that text document',
            'and do not move that text document',
        ) + ' Instead paste the SIPR incident details into the NIPR email.',
        safe + '. You must not complete this transfer until further notice.',
        safe + '. Rather than transfer the draft to SIPR, keep it on NIPR.',
    ]
    for response_text in unsafe_variants:
        result = score(mixed_response(rows).replace(safe, response_text, 1))
        assert not result['passed'], (response_text, result)
        assert any(
            'contradictory or negated' in error
            or 'must not direct SIPR content into NIPR' in error
            for error in result['errors']
        )

    inline = mixed_response(rows).replace(
        'SIPR Transfer Instructions:\nCopy the SIPR recipient',
        'SIPR Transfer Instructions: Copy the SIPR recipient',
        1,
    )
    result = score(inline)
    assert not result['passed'], result
    assert any('SIPR Transfer Instructions label' in error for error in result['errors'])

    correction = mixed_response(rows) + (
        '\n\nCorrection needed: the NIPR row has an ambiguous Network Connection; '
        'do not send until the operator confirms it.'
    )
    result = score(correction)
    assert result['passed'], result

    trailing_variants = [
        'Actually, do not move the text document to SIPR; email it on NIPR instead.',
        'Hold off sending this draft to SIPR; route it through NIPR instead.',
    ]
    for trailing in trailing_variants:
        result = score(mixed_response(rows) + '\n\n' + trailing)
        assert not result['passed'], (trailing, result)
        assert any(
            'revisits SIPR transfer handling' in error
            for error in result['errors']
        )

    benign_variants = [
        safe.replace('into a text document', 'into a text document without changes'),
        safe.replace('move that text document to SIPR', 'move that text document from NIPR to SIPR'),
    ]
    for response_text in benign_variants:
        result = score(mixed_response(rows).replace(safe, response_text, 1))
        assert result['passed'], (response_text, result)

    leading = mixed_response(rows).replace(
        'SIPR Recipient:',
        'Operator note: do not use iSafe; email the SIPR draft from NIPR instead.\n\nSIPR Recipient:',
        1,
    )
    result = score(leading)
    assert not result['passed'], result
    assert any('before SIPR Transfer Instructions' in error for error in result['errors'])

    # Scoring follows ascending date, not CSV row order.
    shuffled = list(reversed(rows))
    scored = module.score_final_response(
        mixed_response(rows), shuffled, start_date=start, end_date=end, previous_count=previous,
    )
    assert scored['passed'], scored
    scored = module.score_final_response(
        mixed_response(shuffled), shuffled, start_date=start, end_date=end, previous_count=previous,
    )
    assert any('ascending date order' in error for error in scored['errors']), scored

    return [
        'transfer_negation_variants',
        'inline_sipr_transfer_label',
        'trailing_source_correction_note',
        'trailing_transfer_contradiction_variants',
        'benign_transfer_phrasing_variants',
        'leading_transfer_contradiction',
        'ascending_date_order',
    ]
