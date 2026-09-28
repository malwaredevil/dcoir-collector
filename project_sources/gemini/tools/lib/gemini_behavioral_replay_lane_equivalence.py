from __future__ import annotations

import re

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_assertive_polarity

_LANE = r"(?:console|shell|environment|execution\s+context)"
_LANES = r"(?:consoles|shells|environments|execution\s+contexts)"
_COMMAND = r"(?:command|commands|command\s+execution|command\s+forms?|command\s+syntax|command\s+syntaxes|syntax|syntaxes|form|forms)"
_CROSS_ENV = (
    rf"(?:(?:the\s+)?other\s+{_LANE}|"
    rf"both\s+(?:execution\s+)?{_LANES}|"
    rf"(?:either|each|any)\s+(?:execution\s+)?{_LANE}|"
    rf"the\s+two\s+{_LANES})"
)
_EQUIVALENT = r"(?:the\s+same|same|equivalent|identical|indistinguishable|interchangeable|compatible|substitutable|portable)"
_EQUIVALENT_MANNER = r"(?:the\s+same|same|identically|equivalently|indistinguishably|interchangeably|compatibly)"
_EXECUTE = r"(?:run|runs|running|execute|executes|executing|work|works|working|function|functions|functioning|use|uses|using)"
_LOCAL_RELATION_NEGATION = re.compile(
    r"\b(?:not|never|cannot|can't|can\s+not|do\s+not|does\s+not|did\s+not|is\s+not|are\s+not|was\s+not|were\s+not|neither)\b",
    re.I,
)

_PATTERNS = (
    # Predicate compatibility attached to command/syntax subjects.
    re.compile(
        rf"\b(?:either|both|each|any|all|these|those|the\s+two)[^.!?;\n]{{0,50}}{_COMMAND}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:can|may|could)?\s*(?:be\s+)?(?:run|executed|used|valid|supported|accepted|usable|interchangeable|compatible|portable|functional|functioning|work|works|run|runs|execute|executes)\b"
        rf"[^.!?;\n]{{0,80}}\b{_CROSS_ENV}\b"
        rf"|\b(?:the\s+)?same\s+(?:command|syntax|form)\b[^.!?;\n]{{0,100}}\b(?:works|runs|executes|functions|is\s+(?:valid|supported|compatible|portable))\b[^.!?;\n]{{0,80}}\b{_CROSS_ENV}\b",
        re.I,
    ),
    # No-difference / no-distinction relations, in either constituent order.
    re.compile(
        rf"\b(?:there\s+is\s+)?(?:no|zero)\s+(?:(?:meaningful|material|practical|operational)\s+)?(?:difference|distinction)\b"
        rf"[^.!?;\n]{{0,100}}\b(?:between\s+(?:the\s+two|both|either)\s+{_LANES}|in\s+{_COMMAND})\b"
        rf"[^.!?;\n]{{0,120}}\b(?:between\s+(?:the\s+two|both|either)\s+{_LANES}|{_COMMAND})\b",
        re.I,
    ),
    # Lane pair itself asserted equivalent for command execution.
    re.compile(
        rf"\b(?:the\s+two|both)\s+{_LANES}\b[^.!?;\n]{{0,60}}\b(?:is|are|remain|seem|operate\s+as)\b"
        rf"[^.!?;\n]{{0,30}}\b{_EQUIVALENT}\b[^.!?;\n]{{0,100}}\b(?:for|in|with\s+respect\s+to)\b[^.!?;\n]{{0,60}}\b{_COMMAND}\b"
        rf"|\b(?:for|in|with\s+respect\s+to)\b[^.!?;\n]{{0,50}}\b{_COMMAND}\b[^.!?;\n]{{0,80}}\b(?:the\s+two|both)\s+{_LANES}\b[^.!?;\n]{{0,50}}\b(?:is|are)\b[^.!?;\n]{{0,20}}\b{_EQUIVALENT}\b",
        re.I,
    ),
    # Command behavior/result equivalence across lanes.
    re.compile(
        rf"\b{_COMMAND}\b[^.!?;\n]{{0,60}}\b(?:behave|behaves|perform|performs|produce|produces|yield|yields|give|gives|return|returns|is|are)\b"
        rf"[^.!?;\n]{{0,40}}\b(?:{_EQUIVALENT}|{_EQUIVALENT_MANNER})\b(?:\s+(?:result|results|outcome|outcomes|effect|effects|behavior|semantics))?"
        rf"[^.!?;\n]{{0,80}}\b(?:in|across|between)\s+{_CROSS_ENV}\b"
        rf"|\b(?:result|results|outcome|outcomes|behavior|semantics)\s+of\s+{_COMMAND}\b[^.!?;\n]{{0,60}}\b(?:is|are)\b[^.!?;\n]{{0,30}}\b{_EQUIVALENT}\b[^.!?;\n]{{0,80}}\b(?:in|across|between)\s+{_CROSS_ENV}\b",
        re.I,
    ),
    # Explicit same-result relation from one lane to the other.
    re.compile(
        rf"\b(?:running|executing|using)\s+(?:the\s+same\s+|a\s+|any\s+)?(?:command|syntax|form)"
        rf"[^.!?;\n]{{0,80}}\bin\s+(?:one|either)\s+{_LANE}"
        rf"[^.!?;\n]{{0,100}}\b(?:gives?|produces?|yields?|has|returns?)\b"
        rf"[^.!?;\n]{{0,40}}\b(?:the\s+same|an?\s+equivalent|an?\s+identical)\s+(?:result|outcome|effect|behavior|semantics?)\b"
        rf"[^.!?;\n]{{0,100}}\b(?:as|to)\b[^.!?;\n]{{0,100}}\b(?:the\s+)?other\s+{_LANE}\b",
        re.I,
    ),
    # Lane substitution / interchangeability.
    re.compile(
        rf"\b(?:one|either)\s+{_LANE}\b[^.!?;\n]{{0,50}}\bis\s+{_EQUIVALENT}\s+(?:with|to)\s+(?:the\s+)?other\b"
        rf"|\b(?:one|either)\s+{_LANE}\b[^.!?;\n]{{0,80}}\b(?:can|may|could)\s+be\s+(?:substituted|interchanged|swapped|replaced)\b[^.!?;\n]{{0,40}}\b(?:for|with)\s+(?:the\s+)?other\b"
        rf"|\b(?:substitute|interchange|swap|replace)\s+(?:one|either)\s+{_LANE}\b[^.!?;\n]{{0,40}}\b(?:for|with)\s+(?:the\s+)?other\b"
        rf"|\b(?:commands?|syntaxes?|forms?)\b[^.!?;\n]{{0,80}}\b(?:can|may|could)\s+be\s+(?:substituted|interchanged|swapped)\b[^.!?;\n]{{0,80}}\b(?:between|across)\s+(?:the\s+two|both|either)\s+{_LANES}\b",
        re.I,
    ),
    # Mirrored implication: what runs/works in one lane also runs/works in the other.
    re.compile(
        rf"\b(?:what|anything|any\s+command|a\s+command|commands?\s+that)\b[^.!?;\n]{{0,60}}\b{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+one\s+{_LANE}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:also\s+)?{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?other\s+{_LANE}\b"
        rf"|\bif\b[^.!?;\n]{{0,80}}\b(?:command|syntax|form)\b[^.!?;\n]{{0,50}}\b{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+one\s+{_LANE}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:then\s+)?(?:it|that\s+(?:command|syntax|form))\b[^.!?;\n]{{0,30}}\b{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?other\s+{_LANE}\b",
        re.I,
    ),
)


def has_affirmative_cross_lane_equivalence(text: str) -> bool:
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if _LOCAL_RELATION_NEGATION.search(match.group(0)):
                continue
            if occurrence_is_assertive_polarity(text, match.start(), match.end()):
                return True
    return False
