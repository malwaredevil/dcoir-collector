from __future__ import annotations

import re

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_asserted

_DIRECTION = r"(?:the\s+other\s+way(?:\s+a?round)?|in\s+reverse(?:\s+too)?|both\s+ways|in\s+both\s+directions)"
_AFFIRM_MOD = r"(?:(?:also|definitely|clearly|certainly|explicitly|actually|really|indeed)\s+)*"
_REFERENT = r"(?:the\s+(?:same|converse|reverse(?:\s+(?:implication|relation(?:ship)?|direction))?|implication|relation(?:ship)?|rule)|this|that|it)"
_PREDICATE = (
    rf"(?:is\s+{_AFFIRM_MOD}(?:true|the\s+case)(?:\s+{_DIRECTION})?"
    rf"|{_AFFIRM_MOD}(?:holds?|applies?|works?|goes?)(?:\s+as\s+well)?(?:\s+{_DIRECTION})?)"
)
# A relative clause counts only when it names the reverse direction itself.
_DIRECTIONAL_PREDICATE = (
    rf"(?:is\s+{_AFFIRM_MOD}true|{_AFFIRM_MOD}(?:holds?|applies?|works?|goes?))"
    rf"(?:\s+as\s+well)?\s+{_DIRECTION}"
)
# "The opposite is true" alone usually rejects the prior claim; only additive
# forms ("and the opposite ...", "the inverse also holds") are reciprocal.
_OPPOSITE = (
    r"(?:and\s+the\s+(?:opposite|inverse)\s+(?:is\s+{m}(?:true|the\s+case)|{m}(?:holds?|applies?))"
    r"|the\s+(?:opposite|inverse)\s+(?:is\s+(?:also|likewise)\s+(?:true|the\s+case)|(?:also|likewise)\s+(?:holds?|applies?)"
    r"|(?:is\s+true|holds?|applies?)\s+(?:too|as\s+well))"
    r"|so\s+does\s+the\s+(?:reverse|converse|opposite|inverse)(?:\s+(?:direction|implication))?)"
).format(m=_AFFIRM_MOD)
# Typographic variants of one token: "vice versa", "vice-versa", non-breaking or dash forms.
_VICE_VERSA = r"vice(?:\s+|\s*[-\u2010-\u2015]\s*)versa"

RECIPROCAL = (
    rf"(?:{_VICE_VERSA}|conversely|reciprocally|(?:and\s+)?the\s+reverse(?!\s+(?:implication|relation(?:ship)?|direction)\b)|in\s+both\s+directions|both\s+ways"
    rf"|(?:and\s+)?the\s+converse\s+(?:too|as\s+well|also)"
    rf"|(?:,\s*|\band\s+)the\s+other\s+way\s+a?round"
    rf"|(?:(?:and|likewise)\s+)+in\s+reverse(?!\s+order\b)"
    rf"|{_REFERENT}\s+{_PREDICATE}"
    rf"|which\s+{_DIRECTIONAL_PREDICATE}|{_OPPOSITE}"
    rf"|(?:(?:this|that|the)\s+(?:relation(?:ship)?|implication)|this|that|it)\s+is\s+{_AFFIRM_MOD}"
    rf"(?:reciprocal|symmetric(?:al)?|bidirectional|two-way|mutual))"
)

_LOCAL_REFERENT = r"(?:(?:this|that|the)(?:\s+(?:relation|relationship|converse|reverse|direction))?\s+)?"
_STRONG_MOD = r"(?:(?:definitely|clearly|certainly|absolutely|plainly|explicitly|actually|really)\s+)*"
_LIMITER = r"(?:always|necessarily|universally|generally|strictly|fully|actually|really)"
_EPISTEMIC = r"(?:probably|possibly|perhaps|apparently|seemingly|likely)"
_PREFIX_NONASSERTIVE = re.compile(
    r"(?:\b(?:may|might|could|would|should)\s+(?:not\s+)?(?:be\s+true|hold|apply|work|go)"
    r"|\b(?:do|does|did)\s+not\s+(?:(?:always|necessarily|universally|generally)\s+)?(?:hold|apply|work|go)"
    r"|\b(?:probably|possibly|perhaps|apparently|seemingly|likely)\s+(?:holds?|applies?|works?|goes?))\s*$",
    re.I,
)

_REJECTION = re.compile(
    rf"^\s*[,;]?\s*(?:but\s+)?{_LOCAL_REFERENT}(?:"
    rf"(?:is|being)\s+{_STRONG_MOD}(?:false|denied|one-way|asymmetric)"
    rf"|(?:is|being)\s+{_STRONG_MOD}(?:by\s+no\s+means|not(?:\s+{_LIMITER})?)\s+(?:true|reciprocal|bidirectional|symmetric)"
    rf"|{_STRONG_MOD}(?:also\s+)?does(?:n't|\s+not)\s+(?:{_LIMITER}\s+)?(?:hold|apply|work)"
    rf"|(?:may|might|could|would|should)\s+(?:not\s+)?(?:be\s+true|hold|apply|work)"
    rf"|is\s+{_EPISTEMIC}\s+(?:true|reciprocal|bidirectional)"
    rf"|(?:not\s+(?:always|necessarily|universally)|only\s+(?:sometimes|conditionally|in\s+some\s+cases))\b"
    rf"|no\s+(?:reciprocal|reverse)\s+(?:relation|relationship)\b"
    rf")",
    re.I,
)


def reciprocal_prefix_rejects(prefix: str) -> bool:
    return bool(_PREFIX_NONASSERTIVE.search(prefix))


def reciprocal_suffix_rejects(suffix: str) -> bool:
    return bool(_REJECTION.match(suffix))


def reciprocal_is_assertive(text: str, match: re.Match[str]) -> bool:
    """A reciprocal is asserted when neither its local frame nor a trailing rejection denies it."""
    start, end = match.start("reciprocal"), match.end("reciprocal")
    if reciprocal_prefix_rejects(text[max(match.start(), start - 80):start]):
        return False
    if not occurrence_is_asserted(text, start, end):
        return False
    return not reciprocal_suffix_rejects(text[end:min(len(text), end + 80)])
