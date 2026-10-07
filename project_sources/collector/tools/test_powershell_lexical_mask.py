#!/usr/bin/env python3
"""Table tests for the shared PowerShell lexical mask and the gates that use it."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import event_text_query_bound_common
import powershell_function_reachability_parsing
import validate_dcoir_runtime_common
from powershell_function_reachability_contract import SourceFile
from powershell_lexical_mask import mask_powershell_non_code

# (label, source, text that must stay visible as code, text that must be masked)
CODE_AFTER_STRING_CASES = [
    ('double quote ending in an escaped backtick', '"a``"; Visible-Cmd', 'Visible-Cmd', 'a``'),
    ('single quote ending in a literal backtick', "'C:\\temp`'; Visible-Cmd", 'Visible-Cmd', 'temp`'),
    ('single quote doubled-quote escape', "'it''s'; Visible-Cmd", 'Visible-Cmd', 'it'),
    ('double quote doubled-quote escape', '"say ""hi"""; Visible-Cmd', 'Visible-Cmd', 'hi'),
    ('double quote backtick-escaped quote', '"a`"Hidden-Cmd"; Visible-Cmd', 'Visible-Cmd', 'Hidden-Cmd'),
    ('line comment', '# Hidden-Cmd\nVisible-Cmd', 'Visible-Cmd', 'Hidden-Cmd'),
    ('block comment', '<# Hidden-Cmd\n #> Visible-Cmd', 'Visible-Cmd', 'Hidden-Cmd'),
    ('single here-string', "@'\nHidden-Cmd 'x' \"y\"\n'@\nVisible-Cmd", 'Visible-Cmd', 'Hidden-Cmd'),
    ('double here-string', '@"\nHidden-Cmd\n"@\nVisible-Cmd', 'Visible-Cmd', 'Hidden-Cmd'),
    ('CRLF here-string', '@"\r\nHidden-Cmd\r\n"@\r\nVisible-Cmd', 'Visible-Cmd', 'Hidden-Cmd'),
]


class MaskTests(unittest.TestCase):
    def test_code_after_strings_and_comments_stays_visible(self) -> None:
        for label, source, visible, hidden in CODE_AFTER_STRING_CASES:
            with self.subTest(label):
                masked = mask_powershell_non_code(source)
                self.assertIn(visible, masked)
                self.assertNotIn(hidden, masked)

    def test_layout_is_preserved(self) -> None:
        for label, source, _visible, _hidden in CODE_AFTER_STRING_CASES:
            with self.subTest(label):
                masked = mask_powershell_non_code(source)
                self.assertEqual(len(masked), len(source))
                self.assertEqual(
                    [i for i, c in enumerate(masked) if c in '\r\n'],
                    [i for i, c in enumerate(source) if c in '\r\n'],
                )

    def test_indented_here_string_terminator_does_not_close(self) -> None:
        source = '@"\nbody\n  "@\nHidden-Cmd\n"@\nVisible-Cmd'
        masked = mask_powershell_non_code(source)
        self.assertNotIn('Hidden-Cmd', masked)
        self.assertIn('Visible-Cmd', masked)

    def test_unterminated_constructs_mask_to_end(self) -> None:
        for source in ('"open Hidden-Cmd', "'open Hidden-Cmd", '<# Hidden-Cmd', '@"\nHidden-Cmd'):
            with self.subTest(source):
                self.assertNotIn('Hidden-Cmd', mask_powershell_non_code(source))

    def test_code_backtick_escapes_are_masked_only_on_request(self) -> None:
        source = 'a`|b'
        self.assertEqual(mask_powershell_non_code(source), source)
        self.assertEqual(mask_powershell_non_code(source, mask_backtick_escapes=True), 'a  b')


class GateTests(unittest.TestCase):
    def test_every_gate_uses_the_shared_mask(self) -> None:
        for module in (
            validate_dcoir_runtime_common,
            event_text_query_bound_common,
            powershell_function_reachability_parsing,
        ):
            with self.subTest(module.__name__):
                self.assertIs(module.mask_powershell_non_code, mask_powershell_non_code)

    def test_convert_to_json_gate_sees_call_after_escaped_backtick_string(self) -> None:
        calls = validate_dcoir_runtime_common.find_convert_to_json_calls(
            'x.ps1', '$a = "a``"; $b | ConvertTo-Json\n'
        )
        self.assertEqual([call['line'] for call in calls], [1])

    def test_event_query_gate_sees_command_after_single_quoted_backtick(self) -> None:
        spans = event_text_query_bound_common.extract_powershell_command_spans(
            "$p = 'C:\\temp`'; Get-WinEvent -LogName System\n", 'Get-WinEvent'
        )
        self.assertEqual(spans, ['Get-WinEvent -LogName System'])

    def test_reachability_fallback_sees_function_after_single_quoted_backtick(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'x.ps1'
            path.write_text("$p = 'C:\\temp`'\nfunction Get-Visible { }\n", encoding='utf-8')
            source = SourceFile(repo_path='x.ps1', path=path, load_order=1)
            keys = powershell_function_reachability_parsing.fallback_function_keys([source])
        self.assertEqual(keys, {'get-visible'})


if __name__ == '__main__':
    unittest.main()
