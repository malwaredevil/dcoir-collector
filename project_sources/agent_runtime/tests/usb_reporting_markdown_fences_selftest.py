from __future__ import annotations


def run_markdown_fence_tests(
    module,
    nipr_fixture,
    mixed_fixture,
    nipr_builder,
    mixed_builder,
    start: str,
    end: str,
    previous: int,
) -> list[str]:
    names: list[str] = []
    for fixture, builder in ((nipr_fixture, nipr_builder), (mixed_fixture, mixed_builder)):
        rows = module.load_fixture_rows(fixture)
        base = builder(rows)
        for opener_len in (4, 5):
            hostile = base.replace('```text', '`' * opener_len + 'text', 1)
            result = module.score_final_response(hostile, rows, start_date=start, end_date=end, previous_count=previous)
            assert not result['passed'], (opener_len, result)
            assert any('matching fence' in error for error in result['errors']), result
        for fence_len in (4, 5):
            valid = base.replace('```', '`' * fence_len)
            result = module.score_final_response(valid, rows, start_date=start, end_date=end, previous_count=previous)
            assert result['passed'], (fence_len, result)
        tilde = base.replace('```', '~~~')
        result = module.score_final_response(tilde, rows, start_date=start, end_date=end, previous_count=previous)
        assert not result['passed'], result
        longer_close = base.replace('\n```\n', '\n````\n', 1)
        result = module.score_final_response(longer_close, rows, start_date=start, end_date=end, previous_count=previous)
        assert result['passed'], result
        bad_info = base.replace('```text', '```te`xt', 1)
        result = module.score_final_response(bad_info, rows, start_date=start, end_date=end, previous_count=previous)
        assert not result['passed'], result
        for indent in ('\t', ' \t', '  \t', '   \t'):
            bad_open = base.replace('```text', indent + '```text', 1)
            result = module.score_final_response(bad_open, rows, start_date=start, end_date=end, previous_count=previous)
            assert not result['passed'], (repr(indent), result)
            bad_both = bad_open.replace('\n```\n', '\n' + indent + '```\n', 1)
            result = module.score_final_response(bad_both, rows, start_date=start, end_date=end, previous_count=previous)
            assert not result['passed'], (repr(indent), result)
        for spaces in (' ', '  ', '   '):
            valid_indent = base.replace('```text', spaces + '```text', 1).replace('\n```\n', '\n' + spaces + '```\n', 1)
            result = module.score_final_response(valid_indent, rows, start_date=start, end_date=end, previous_count=previous)
            assert result['passed'], (repr(spaces), result)
    names.append('markdown_fence_delimiter_and_indent_semantics')

    nipr_rows = module.load_fixture_rows(nipr_fixture)
    nipr = nipr_builder(nipr_rows)
    for outer in ('````', '`````', '~~~~', '~~~~~'):
        enclosed = nipr.replace('Subject:', outer + '\nSubject:', 1) + '\n' + outer
        result = module.score_final_response(enclosed, nipr_rows, start_date=start, end_date=end, previous_count=previous)
        assert not result['passed'], (outer, result)
    unclosed = nipr.replace('Subject:', '````\nSubject:', 1)
    result = module.score_final_response(unclosed, nipr_rows, start_date=start, end_date=end, previous_count=previous)
    assert not result['passed'], result

    mixed_rows = module.load_fixture_rows(mixed_fixture)
    mixed = mixed_builder(mixed_rows)
    for outer in ('````', '`````', '~~~~', '~~~~~'):
        enclosed = mixed.replace('NIPR Subject:', outer + '\nNIPR Subject:', 1)
        enclosed = enclosed.replace('SIPR Recipient:', outer + '\nSIPR Recipient:', 1)
        result = module.score_final_response(enclosed, mixed_rows, start_date=start, end_date=end, previous_count=previous)
        assert not result['passed'], (outer, result)
    names.append('enclosing_markdown_fence_ownership')
    return names
