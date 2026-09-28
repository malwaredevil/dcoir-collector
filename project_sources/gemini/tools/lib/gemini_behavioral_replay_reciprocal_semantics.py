from __future__ import annotations

import re

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
# Typographic variants of one token: "vice versa", "vice-versa", non-breaking or dash forms.
_VICE_VERSA = r"vice(?:\s+|\s*[-\u2010-\u2015]\s*)versa"

RECIPROCAL = (
    rf"(?:{_VICE_VERSA}|conversely|reciprocally|(?:and\s+)?the\s+reverse(?!\s+(?:implication|relation(?:ship)?|direction)\b)|in\s+both\s+directions|both\s+ways"
    rf"|(?:and\s+)?the\s+converse\s+(?:too|as\s+well|also)"
    rf"|(?:,\s*|\band\s+)the\s+other\s+way\s+a?round"
    rf"|(?:(?:and|likewise)\s+)+in\s+reverse(?!\s+order\b)"
    rf"|{_REFERENT}\s+{_PREDICATE}"
    rf"|which\s+{_DIRECTIONAL_PREDICATE}"
    rf"|(?:this|that|the)\s+(?:relation(?:ship)?|implication)\s+is\s+{_AFFIRM_MOD}"
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
