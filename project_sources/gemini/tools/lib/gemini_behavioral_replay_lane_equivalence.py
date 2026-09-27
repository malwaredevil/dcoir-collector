from __future__ import annotations

import re

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_assertive_polarity

_SUBJECT = r"(?:either|both|each|any|all|these|those|the\s+two)"
_COMMAND_KIND = r"(?:commands?|command\s+forms?|kinds?(?:\s+of\s+command)?|(?:command\s+)?syntaxes?|forms?)"
_EQUIVALENCE_SUBJECT = rf"(?:{_SUBJECT}[^.!?;\n]{{0,40}}{_COMMAND_KIND}|(?:the\s+)?same\s+(?:command|syntax|form))"
_COMPATIBILITY = (
    r"(?:(?:can|may|could)\s+be\s+(?:run|executed|used)|"
    r"work(?:s)?|run(?:s)?|execute(?:s)?|function(?:s)?|"
    r"(?:is|are)\s+(?:valid|supported|accepted|usable|interchangeable|compatible|portable))"
)
_CROSS_ENV = (
    r"(?:(?:the\s+)?other\s+(?:console|shell|environment|context)|"
    r"(?:both|either|each|any)\s+(?:execution\s+)?(?:environments?|consoles?|shells?|contexts?)|"
    r"the\s+two\s+(?:environments?|consoles?|shells?|contexts?))"
)

_AFFIRMATIVE_CROSS_LANE_OVERRIDE = re.compile(
    rf"\b{_EQUIVALENCE_SUBJECT}\b[^.!?;\n]{{0,100}}\b{_COMPATIBILITY}\b[^.!?;\n]{{0,80}}\b{_CROSS_ENV}\b"
    rf"|\b{_SUBJECT}\s+(?:kind|form|syntax|command\s+form)s?\b"
    rf"[^.!?;\n]{{0,100}}\b{_CROSS_ENV}\b",
    re.I,
)


def has_affirmative_cross_lane_equivalence(text: str) -> bool:
    return any(
        occurrence_is_assertive_polarity(text, match.start(), match.end())
        for match in _AFFIRMATIVE_CROSS_LANE_OVERRIDE.finditer(text)
    )
