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
    r"(?:\s+\w+){0,4}\s+(?:it|(?:that|the)\s+text\s+document|text\s+document|"
    r"(?:the\s+)?(?:sipr\s+)?(?:message\s+)?draft)\b"
)
# Hard NIPR destinations; on/in NIPR may be governed staging before an explicit move to SIPR.
NIPR_DESTINATION = r"\b(?:to|into|onto|via|through|over)\s+(?:the\s+)?nipr\b"
ANAPHORIC_REVOCATION = (
    r"\b(?:do not|don't|must not|shall not|should not|cannot|can't|never)\s+"
    r"(?:do\s+(?:so|that|it)|proceed|continue)\b|"
    r"\b(?:this|that|it)\s+(?:must not|shall not|should not|cannot|can't)\s+"
    r"(?:happen|occur|proceed|continue)\b"
)
GENERIC_TRANSFER_REVOCATION = (
    r"\b(?:disregard|ignore|cancel|revoke|revoked|withdraw|override|reverse)\b"
    r".{0,48}\b(?:transfer|instruction|instructions|preceding|above)\b|"
    r"\b(?:preceding|above)\b.{0,32}\b(?:instruction|instructions)\b.{0,24}"
    r"\b(?:revoked|cancelled|canceled|withdrawn|overridden|reversed)\b"
)
PREDICATE_TRANSFER_REVOCATION = (
    r"\b(?:this transfer|that transfer|the transfer|this instruction|that instruction|"
    r"the preceding instruction|the instruction above|the above instruction|the previous instruction|"
    r"this direction|that direction|the preceding direction|the direction above|the above direction)\b.{0,24}"
    r"(?:(?:is|are|was|were|has been|have been)\s+(?:(?:no longer|not)\s+"
    r"(?:valid|authorized|authorised|permitted|allowed|applicable|effective|approved)|"
    r"(?:invalid|unauthorized|unauthorised|forbidden|prohibited|rescinded|nullified|voided))\b|"
    r"(?:no longer|does not|doesn't)\s+(?:appl(?:y|ies)|stand(?:s)?|govern(?:s)?|authori[sz]e(?:s)?|permit(?:s)?)\b)"
)


def _normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def _clause_has_transfer_negation(clause: str) -> bool:
    if re.search(ANAPHORIC_REVOCATION, clause) or re.search(WITHOUT_TRANSFER_ACTION, clause):
        return True
    negation = re.search(TRANSFER_NEGATION, clause)
    if not negation:
        return False
    return bool(re.search(TRANSFER_ACTION, clause[negation.end():]))


def _has_transfer_contradiction(text: str) -> bool:
    if re.search(GENERIC_TRANSFER_REVOCATION, text) or re.search(PREDICATE_TRANSFER_REVOCATION, text):
        return True
    return any(
        _clause_has_transfer_negation(clause)
        for clause in re.split(r'[.;!?]+', text)
        if clause.strip()
    )


def _has_unsafe_nipr_destination(text: str) -> bool:
    if re.search(NIPR_DESTINATION, text):
        return True
    for match in re.finditer(r'\b(?:on|in)\s+(?:the\s+)?nipr\b', text):
        before = text[max(0, match.start() - 32):match.start()]
        after = text[match.end():]
        staged_document = re.search(r'\btext document\s*$', before)
        governed_move = re.search(
            r'\bmove\b.{0,64}\b(?:that text document|the text document|it)\b'
            r'.{0,48}\bto sipr\b.{0,64}\bintelink isafe\b', after,
        )
        if not (staged_document and governed_move):
            return True
    return False


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
    if _has_unsafe_nipr_destination(text):
        errors.append('SIPR transfer instructions must not direct SIPR content into NIPR')
    return errors


def prose_outside_blocks(text: str, labels: set[str]) -> str:
    """Free prose left after removing fenced code blocks and governed label lines."""
    text = re.sub(r'(?ms)^```[^\n]*\n.*?^```[ \t]*$', '', text)
    return '\n'.join(line for line in text.splitlines() if line.strip().rstrip(':') not in labels)


def trailing_revisits_transfer_handling(trailing: str) -> bool:
    text = _normalized(trailing)
    if (re.search(ANAPHORIC_REVOCATION, text) or re.search(GENERIC_TRANSFER_REVOCATION, text)
            or re.search(PREDICATE_TRANSFER_REVOCATION, text)):
        return True
    if re.search(r'isafe|text document|sipr (?:recipient|subject|message draft)', text):
        return True
    return any(
        'sipr' in sentence and (
            re.search(TRANSFER_ACTION, sentence) or re.search(TRANSFER_NEGATION, sentence)
        )
        for sentence in re.split(r'(?<=[.!?])\s+', text)
    )
