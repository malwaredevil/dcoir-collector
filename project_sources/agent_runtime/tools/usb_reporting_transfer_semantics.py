#!/usr/bin/env python3
from __future__ import annotations

import re

TRANSFER_NEGATION = (
    r"\b(?:do not|don't|must not|shall not|should not|cannot|can't|no longer|never|avoid|"
    r"instead(?: of)?|rather than|refrain from|skip|hold off)\b"
)
TRANSFER_ACTION = (
    r"\b(?:transfer|transferring|send|sending|move|moving|copy|copying|upload|uploading|"
    r"attach|attaching|route|routing|deliver|delivering|perform|performing|complete|completing)\b"
)
WITHOUT_TRANSFER_ACTION = (
    r"\bwithout\b(?:\s+\w+){0,3}\s+"
    r"(?:moving|transferring|sending|uploading|copying|attaching|routing|delivering)\b"
)
# Only a NIPR destination is unsafe; "from NIPR to SIPR" is the governed direction.
NIPR_DESTINATION = r"\b(?:to|into|onto|on|via|through|over|in)\s+(?:the\s+)?nipr\b"


def _normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def _clause_has_transfer_negation(clause: str) -> bool:
    if re.search(WITHOUT_TRANSFER_ACTION, clause):
        return True
    negation = re.search(TRANSFER_NEGATION, clause)
    if not negation:
        return False
    return bool(re.search(TRANSFER_ACTION, clause[negation.end():]))


def _has_transfer_contradiction(text: str) -> bool:
    return any(
        _clause_has_transfer_negation(clause)
        for clause in re.split(r'[.;!?]+', text)
        if clause.strip()
    )


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
    if _has_transfer_contradiction(text):
        errors.append('SIPR transfer instructions contain contradictory or negated handling')
    if re.search(NIPR_DESTINATION, text):
        errors.append('SIPR transfer instructions must not direct SIPR content into NIPR')
    return errors


def prose_outside_blocks(text: str, labels: set[str]) -> str:
    """Free prose left after removing fenced code blocks and governed label lines."""
    text = re.sub(r'(?ms)^```[^\n]*\n.*?^```[ \t]*$', '', text)
    return '\n'.join(line for line in text.splitlines() if line.strip().rstrip(':') not in labels)


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
