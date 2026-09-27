#!/usr/bin/env python3
from __future__ import annotations

import re

TRANSFER_NEGATION = (
    r"\b(?:do not|don't|must not|shall not|should not|cannot|can't|no longer|never|avoid|"
    r"instead(?: of)?|rather than|refrain from|skip|hold off)\b"
)
TRANSFER_ACTION = (
    r"\b(?:transfer|transferring|send|sending|move|moving|copy|copying|upload|uploading|"
    r"attach|attaching|route|routing|deliver|delivering|perform|performing|complete|completing|"
    r"e-?mail|e-?mailing|transmit|transmitting|forward|forwarding|paste|pasting|submit|submitting)\b"
)
WITHOUT_TRANSFER_ACTION = (
    r"\bwithout\b(?:\s+\w+){0,3}\s+"
    r"(?:moving|transferring|sending|uploading|copying|attaching|routing|delivering)\b"
    r"(?:\s+\w+){0,4}\s+(?:it|(?:that|the)\s+text\s+document|text\s+document|"
    r"(?:the\s+)?(?:sipr\s+)?(?:message\s+)?draft)\b"
)
# The governed material versus explicitly unrelated material a restriction may exclude.
GOVERNED_OBJECT = (
    r"\b(?:it|text document|document|draft|sipr (?:recipient|subject|message draft)|"
    r"transfer|instructions?)\b"
)
UNRELATED_OBJECT = r"\b(?:unrelated|other|additional|extra|non-governed|else)\b"
# Hard NIPR destinations/channels; on/in NIPR may be governed staging before an explicit move to SIPR.
NIPR_DESTINATION = (
    r"\b(?:to|into|onto|via|through|over|using|by|within|across)\s+(?:the\s+)?nipr\b|"
    r"\bnipr\s+(?:e-?mail|mail|inbox|channel)\b"
)
ANAPHORIC_REVOCATION = (
    r"\b(?:do not|don't|must not|shall not|should not|cannot|can't|never)\s+"
    r"(?:do\s+(?:so|that|it)|proceed|continue)\b|"
    r"\b(?:this|that|it)\s+(?:must not|shall not|should not|cannot|can't)\s+"
    r"(?:happen|occur|proceed|continue)\b"
)
REVOKED_STATE = (
    r"(?:revoked|rescinded|nullified|voided|void|annulled|cancell?ed|withdrawn|overridden|overruled|"
    r"reversed|superseded|retracted|countermanded|replaced|invalid|unauthori[sz]ed|forbidden|prohibited)"
)
GENERIC_TRANSFER_REVOCATION = (
    r"\b(?:disregard|ignore|cancel|revoke|withdraw|override|overrule|reverse|supersede|retract|"
    r"rescind|nullify|void|annul|countermand)\b"
    r".{0,48}\b(?:transfer|instruction|instructions|preceding|above)\b|"
    r"\b(?:preceding|above)\b.{0,32}\b(?:instruction|instructions)\b.{0,24}\b" + REVOKED_STATE + r"\b"
)
TRANSFER_REFERENT = (
    r"\b(?:this|that|these|those|the|above|preceding|previous|prior|earlier)\s+"
    r"(?:(?:above|preceding|previous|prior|earlier|sipr|isafe|transfer)\s+){0,2}"
    r"(?:transfer|instructions?|directions?|directives?|step|guidance)\b"
)
PREDICATE_TRANSFER_REVOCATION = (
    TRANSFER_REFERENT + r".{0,24}?"
    r"(?:(?:is|are|was|were|has been|have been)\s+(?:(?:hereby|now|officially|formally)\s+)?"
    r"(?:(?:no longer|not)\s+(?:valid|authorized|authorised|permitted|allowed|applicable|effective|"
    r"approved|in effect)|" + REVOKED_STATE + r")\b|"
    r"(?:no longer|does not|doesn't|do not|don't)\s+(?:appl(?:y|ies)|stand(?:s)?|govern(?:s)?|"
    r"authori[sz]e(?:s)?|permit(?:s)?)\b)"
)


def _restricts_unrelated_material(complement: str) -> bool:
    """A restriction whose object is only unrelated material does not revoke the transfer."""
    complement = re.split(r"\b(?:and|but|or)\b", complement, maxsplit=1)[0]
    if re.match(r"\s*to\s+(?:proceed|continue|occur|happen|go|take|be|start|begin)\b", complement):
        return False
    return bool(re.search(UNRELATED_OBJECT, complement)) and not re.search(GOVERNED_OBJECT, complement)


def _normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def transfer_continuation_is_governed(text: str) -> bool:
    """Return whether a same-line post-iSafe continuation is still transfer handling."""
    normalized = _normalized(text)
    if not normalized:
        return True
    context = re.search(
        r'\b(?:sipr|isafe|text document|message draft|recipient|subject|nipr|'
        r'unrelated|other|additional|extra|material|files?)\b',
        normalized,
    )
    return bool(context and re.search(TRANSFER_ACTION, normalized))


def same_line_transfer_prose(transfer: str, isafe_url: str) -> str:
    """Return same-line content that is not governed transfer handling."""
    protected = re.sub(re.escape(isafe_url), 'INTELINK_ISAFE_URL', transfer, flags=re.I)
    fragments = [
        fragment.strip(' .;')
        for fragment in re.split(r'(?<=[.!?])\s+', protected)
        if fragment.strip(' .;')
    ]
    residual = [
        fragment.replace('INTELINK_ISAFE_URL', isafe_url)
        for fragment in fragments
        if not transfer_continuation_is_governed(fragment)
    ]
    unsupported = re.compile(
        r'\b(?:correction|source correction|approval status)\s*:'
        r'|\bapproval\s+status\b.{0,32}\b(?:approved|authorized|cleared|exempt|compliant)\b'
        r'|\b(?:incidents?|devices?|violations?|users?)\b.{0,64}\b(?:approved|authorized|cleared|exempt|compliant)\b'
        r'|\b(?:approved|authorized|cleared|exempt|compliant)\b.{0,64}\b(?:incidents?|devices?|violations?|users?)\b'
        r'|\bno\s+policy\s+violation(?:\s+occurred)?\b',
        re.I,
    )
    residual.extend(match.group(0) for match in unsupported.finditer(transfer))
    return '\n'.join(dict.fromkeys(item for item in residual if item.strip()))


def _clause_has_transfer_negation(clause: str) -> bool:
    if re.search(ANAPHORIC_REVOCATION, clause) or re.search(WITHOUT_TRANSFER_ACTION, clause):
        return True
    negation = re.search(TRANSFER_NEGATION, clause)
    if not negation:
        return False
    action = re.search(TRANSFER_ACTION, clause[negation.end():])
    if not action:
        return False
    return not _restricts_unrelated_material(clause[negation.end() + action.end():])


def _has_predicate_revocation(text: str) -> bool:
    return any(
        not _restricts_unrelated_material(text[match.end():].split('.', 1)[0])
        for match in re.finditer(PREDICATE_TRANSFER_REVOCATION, text)
    )


def _has_transfer_contradiction(text: str) -> bool:
    if re.search(GENERIC_TRANSFER_REVOCATION, text) or _has_predicate_revocation(text):
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
    # Intelink iSafe is the only governed delivery path; any address or NIPRNet channel adds another.
    if re.search(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\bniprnet\b', text):
        errors.append('SIPR transfer instructions must not add another delivery address or NIPRNet channel')
    return errors


def prose_outside_blocks(text: str, labels: set[str]) -> str:
    """Free prose left after removing fenced code blocks and governed label lines."""
    text = re.sub(r'(?ms)^```[^\n]*\n.*?^```[ \t]*$', '', text)
    return '\n'.join(line for line in text.splitlines() if line.strip().rstrip(':') not in labels)


def trailing_revisits_transfer_handling(trailing: str) -> bool:
    text = _normalized(trailing)
    if (re.search(ANAPHORIC_REVOCATION, text) or re.search(GENERIC_TRANSFER_REVOCATION, text)
            or _has_predicate_revocation(text)):
        return True
    if re.search(r'isafe|text document|sipr (?:recipient|subject|message draft)', text):
        return True
    return any(
        'sipr' in sentence and (
            re.search(TRANSFER_ACTION, sentence) or re.search(TRANSFER_NEGATION, sentence)
        )
        for sentence in re.split(r'(?<=[.!?])\s+', text)
    )
