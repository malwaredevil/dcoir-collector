from __future__ import annotations

import re

_DIRECTION = r"(?:the\s+other\s+way(?:\s+around)?|in\s+reverse(?:\s+too)?|both\s+ways|in\s+both\s+directions)"
_AFFIRM_MOD = r"(?:(?:also|definitely|clearly|certainly|explicitly|actually|really|indeed)\s+)*"
_REFERENT = r"(?:the\s+(?:same|converse|reverse(?:\s+implication)?|implication|relation(?:ship)?|rule)|this|that|it)"
_PREDICATE = (
    rf"(?:is\s+{_AFFIRM_MOD}true(?:\s+{_DIRECTION})?"
    rf"|{_AFFIRM_MOD}(?:holds?|applies?|works?|goes?)(?:\s+as\s+well)?(?:\s+{_DIRECTION})?)"
)

RECIPROCAL = (
    rf"(?:vice\s+versa|conversely|reciprocally|(?:and\s+)?the\s+reverse"
    rf"|{_REFERENT}\s+{_PREDICATE}"
    rf"|(?:this|that|the)\s+relation(?:ship)?\s+is\s+{_AFFIRM_MOD}reciprocal)"
)

_LOCAL_REFERENT = r"(?:(?:this|that|the)(?:\s+(?:relation|relationship|converse|reverse|direction))?\s+)?"
_STRONG_MOD = r"(?:(?:definitely|clearly|certainly|absolutely|plainly|explicitly|actually|really)\s+)*"
_LIMITER = r"(?:always|necessarily|universally|generally|strictly|fully|actually|really)"
_EPISTEMIC = r"(?:probably|possibly|perhaps|apparently|seemingly|likely)"
_REJECTION = re.compile(
    rf"^\s*[,;]?\s*(?:but\s+)?{_LOCAL_REFERENT}(?:"
    rf"is\s+{_STRONG_MOD}(?:false|denied|one-way|asymmetric)"
    rf"|is\s+{_STRONG_MOD}(?:by\s+no\s+means|not(?:\s+{_LIMITER})?)\s+(?:true|reciprocal|bidirectional|symmetric)"
    rf"|{_STRONG_MOD}(?:also\s+)?does(?:n't|\s+not)\s+(?:{_LIMITER}\s+)?(?:hold|apply|work)"
    rf"|(?:may|might|could|would|should)\s+(?:not\s+)?(?:be\s+true|hold|apply|work)"
    rf"|is\s+{_EPISTEMIC}\s+(?:true|reciprocal|bidirectional)"
    rf"|(?:not\s+(?:always|necessarily|universally)|only\s+(?:sometimes|conditionally|in\s+some\s+cases))\b"
    rf"|no\s+(?:reciprocal|reverse)\s+(?:relation|relationship)\b"
    rf")",
    re.I,
)


def reciprocal_suffix_rejects(suffix: str) -> bool:
    return bool(_REJECTION.match(suffix))
