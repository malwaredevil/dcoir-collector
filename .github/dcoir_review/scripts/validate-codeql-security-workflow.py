#!/usr/bin/env python3
"""Validate the DCOIR CodeQL security workflow shape without requiring GitHub Actions."""
from __future__ import annotations

import sys
from pathlib import Path

WORKFLOW = Path('.github/workflows/codeql-security.yml')
REUSABLE = Path('.github/workflows/reusable-codeql-security.yml')

REQUIRED_SNIPPETS = {
    WORKFLOW: [
        'name: 27 Security - CodeQL',
        'security-events: write',
        'uses: ./.github/workflows/reusable-codeql-security.yml',
    ],
    REUSABLE: [
        'workflow_call:',
        'github/codeql-action/init@v4',
        'github/codeql-action/analyze@v4',
        'security-extended,security-and-quality',
        '- python',
        '- actions',
        'actions/upload-artifact@v7',
        'actions/download-artifact@v8',
        'name: chatgpt-workflow-report-section-${{ matrix.language }}',
        'pattern: chatgpt-workflow-report-section-*',
        'name: chatgpt-workflow-report-section',
    ],
}

FORBIDDEN_SNIPPETS = {
    REUSABLE: [
        './.github/actions/upload-chatgpt-artifact',
        'actions/upload-artifact@v6',
        'if: ${{ always() && matrix.language == \'python\' }}',
    ],
}


def main() -> int:
    findings: list[str] = []
    for path, snippets in REQUIRED_SNIPPETS.items():
        if not path.exists():
            findings.append(f'{path}: missing required workflow file')
            continue
        text = path.read_text(encoding='utf-8')
        for snippet in snippets:
            if snippet not in text:
                findings.append(f'{path}: missing expected snippet: {snippet}')
        for snippet in FORBIDDEN_SNIPPETS.get(path, []):
            if snippet in text:
                findings.append(f'{path}: contains forbidden snippet: {snippet}')
    if findings:
        print('CodeQL workflow config validation failed:')
        for finding in findings:
            print(f'- {finding}')
        return 1
    print('PASS: CodeQL workflow config validation completed successfully.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
