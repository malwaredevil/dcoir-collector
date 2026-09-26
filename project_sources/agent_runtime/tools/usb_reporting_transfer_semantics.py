#!/usr/bin/env python3
from __future__ import annotations

import re

TRANSFER_NEGATION = (
    r"\b(?:do not|don't|must not|shall not|should not|cannot|can't|no longer|never|avoid|"
    r"instead(?: of)?|rather than|without|refrain from|skip|hold off)\b"
)
TRANSFER_ACTION = r"\b(?:transfer|send|move|copy|upload|attach|route|deliver)\w*\b"
TRANSFER_SCOPE = r"\b(?:sipr|isafe|text document|transfer|copy|move|send|upload|attach|draft)\b"


def _normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def transfer_instruction_errors(transfer: str, isafe_url: str) -> list[str]:
    errors: list[str] = []
    text = _normalized(transfer)
    if isafe_url.lower() not in text:
        errors.append('SIPR transfer instructions lack governed Intelink iSafe URL')
    for phrase in ('sipr recipient', 'sipr subject', 'sipr message draft', 'text document', 'intelink isafe'):
        if phrase not in text:
            errors.append(f'SIPR transfer instructions lack required affirmative element: {phrase}')
    if not re.search(
        r'\bcopy\b.*\bsipr recipient\b.*\bsipr subject\b.*'
        r'\bsipr message draft\b.*\btext document\b',
        text,
    ):
        errors.append('SIPR transfer instructions do not affirmatively copy the governed SIPR draft into a text document')
    if not re.search(
        r'\bmove\b.*\b(?:that text document|the text document|it)\b.*'
        r'\bto sipr\b.*\bintelink isafe\b',
        text,
    ):
        errors.append('SIPR transfer instructions do not affirmatively move the text document to SIPR using Intelink iSafe')
    if re.search(TRANSFER_NEGATION, text) and re.search(TRANSFER_SCOPE, text):
        errors.append('SIPR transfer instructions contain contradictory or negated handling')
    if re.search(r'\bnipr\b', text):
        errors.append('SIPR transfer instructions must not direct SIPR content into NIPR')
    return errors


def trailing_revisits_transfer_handling(trailing: str) -> bool:
    text = _normalized(trailing)
    if re.search(r'isafe|text document|sipr (?:recipient|subject|message draft)', text):
        return True
    return any(
        'sipr' in sentence and (
            re.search(TRANSFER_ACTION, sentence) or re.search(TRANSFER_NEGATION, sentence)
        )
        for sentence in re.split(r'(?<=[.!?])\s+', text)
    )
