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
_EQUIVALENT = r"(?:the\s+same|same|equal|equivalent|identical|indistinguishable|interchangeable|compatible|substitutable|portable)"
_EQUIVALENT_MANNER = r"(?:the\s+same|same|equally|identically|equivalently|indistinguishably|interchangeably|compatibly)"
_EXECUTE = r"(?:run|runs|running|execute|executes|executing|work|works|working|function|functions|functioning|use|uses|using)"
_RELATION_NOUN = r"(?:equivalence|parity|interchangeability|compatibility|sameness|identity)"
_CAPABILITY_OBJECT = r"(?:(?:(?:supported|available|accepted)[-\s]+)?commands?|(?:supported[-\s]+)?command\s+(?:sets?|capabilit(?:y|ies)|repertoires?|availability|inventor(?:y|ies))|sets?\s+of\s+commands?)"
_CAPABILITY_EQUIV = rf"(?:(?:exactly|precisely)\s+(?:the\s+same|matching)|(?:the\s+)?(?:exact|precise)\s+same|all\s+the\s+same|the\s+same|identical|equal|matching|(?:completely|fully)\s+overlapping)\s+{_CAPABILITY_OBJECT}"
_CAPABILITY_VERB = r"(?:support|supports|accept|accepts|allow|allows|expose|exposes|provide|provides|offer|offers|have|has|implement|implements|recognize|recognizes)"
_CAPABILITY_RELATION = r"(?:support(?:ed|s)?|accept(?:ed|s)?|allow(?:ed|s)?|expos(?:e|ed|es)|provid(?:e|ed|es)|availab(?:le|ility))"
_RECIPROCAL = (
    r"(?:vice\s+versa|conversely|"
    r"(?:the\s+)?converse\s+(?:is\s+(?:also\s+)?true|(?:also\s+)?holds?)|"
    r"(?:and\s+the\s+reverse|the\s+reverse\s+(?:is\s+(?:also\s+)?true|(?:also\s+)?holds?))|"
    r"(?:this|that|the\s+(?:same\s+)?relation(?:ship)?)\s+(?:(?:also\s+)?(?:applies|holds)\s+)?in\s+reverse(?:\s+too)?|"
    r"(?:this|that|the)\s+relation(?:ship)?\s+is\s+reciprocal|"
    r"in\s+both\s+directions)"
)
_RECIPROCAL_REJECTION_AFTER = re.compile(
    r"^\s*,?\s*(?:(?:this|that|the)(?:\s+(?:relation|relationship|converse|reverse|direction))?\s+)?"
    r"(?:(?:is\s+(?:not(?:\s+necessarily)?\s+(?:true|reciprocal)|false|denied|one-way|asymmetric))"
    r"|(?:also\s+)?does(?:n't|\s+not)(?:\s+necessarily)?\s+(?:hold|apply)"
    r"|(?:may|might|could|would|should)\s+(?:not\s+)?(?:be\s+true|hold|apply))\b"
    r"|^\s*,?\s*no\s+(?:reciprocal|reverse)\s+(?:relation|relationship)\b",
    re.I,
)
_CAPABILITY_COMPLEMENT_EQUIV = (
    rf"(?:no\s+commands?\s+(?:is|are)\s+(?:unique|exclusive)\s+to\s+(?:either|one)\s+{_LANE}"
    rf"|(?:the\s+two|both)\s+{_LANES}\s+(?:have|support)\s+no\s+(?:unique|exclusive)\s+commands?"
    rf"|neither\s+{_LANE}\s+(?:has|supports)\s+commands?\s+(?:that\s+)?(?:the\s+)?other\s+"
    rf"(?:lacks|does\s+not\s+have|doesn't\s+have))"
)
_RELATION_MARKER = re.compile(
    rf"\b(?:"
    rf"(?:no|zero)\s+(?:(?:meaningful|material|practical|operational)\s+)?(?:difference|distinction)"
    rf"|{_RELATION_NOUN}|{_EQUIVALENT}|{_EQUIVALENT_MANNER}"
    rf"|{_CAPABILITY_EQUIV}"
    rf"|(?:equals?|matches?)"
    rf"|(?:coincide(?:s)?|(?:completely|fully)\s+overlap(?:s)?)"
    rf"|{_CAPABILITY_COMPLEMENT_EQUIV}"
    rf"|(?:can|may|could)\s+be\s+(?:run|executed|used|substituted|interchanged|swapped|replaced)"
    rf"|(?:is|are|remain|seem)\s+{_EQUIVALENT}"
    rf"|(?:works?|runs?|executes?|functions?)"
    rf"|(?:behave|behaves|perform|performs)\s+(?:{_EQUIVALENT}|{_EQUIVALENT_MANNER})"
    rf"|(?:gives?|produces?|yields?|returns?)\s+(?:the\s+same|an?\s+equivalent|an?\s+identical)\s+(?:result|outcome|effect|behavior|semantics?)"
    rf"|(?:substituted|interchanged|swapped|replaced)"
    rf")\b",
    re.I,
)


_PATTERNS = (
    # A one-way capability relation plus an affirmative discourse-level
    # reciprocal establishes equality without repeating the reverse clause.
    re.compile(
        rf"\b(?:(?:every|all)\s+commands?[^.!?\n]{{0,90}}\b{_CAPABILITY_RELATION}\b"
        rf"|(?:(?:the\s+)?(?:local|endpoint)|one|either)?\s*(?:shell|console|environment)[^.!?\n]{{0,60}}\b{_CAPABILITY_VERB}\b"
        rf"[^.!?\n]{{0,90}}\b(?:commands?|syntax(?:es)?)\b)"
        rf"[^!?\n]{{0,100}}(?:,|;|\band\b|\.)?\s*(?P<reciprocal>{_RECIPROCAL})\b",
        re.I,
    ),
    # Equal/shared command capability or identical supported-command sets.
    re.compile(
        rf"\b(?:the\s+two|both)\s+{_LANES}\b[^.!?;\n]{{0,60}}\b{_CAPABILITY_VERB}\b"
        rf"[^.!?;\n]{{0,50}}\b{_CAPABILITY_EQUIV}\b"
        rf"|\b(?:supported|available|accepted|exposed|provided|offered)\s+{_COMMAND}\b"
        rf"[^.!?;\n]{{0,60}}\b(?:is|are|remain)\b[^.!?;\n]{{0,30}}\b(?:the\s+same|identical|equal)\b"
        rf"[^.!?;\n]{{0,80}}\b(?:across|between|in)\s+(?:the\s+two|both)\s+{_LANES}\b"
        rf"|\b(?:command\s+(?:sets?|capabilit(?:y|ies)|availability)|supported\s+commands?)\b"
        rf"[^.!?;\n]{{0,60}}\b(?:is|are|remain)\b[^.!?;\n]{{0,30}}\b(?:the\s+same|identical|equal)\b"
        rf"[^.!?;\n]{{0,80}}\b(?:across|between)\s+(?:the\s+two|both)\s+{_LANES}\b"
        rf"|\b(?:the\s+)?{_CAPABILITY_OBJECT}\s+of\s+(?:the\s+two|both)\s+{_LANES}\b"
        rf"[^.!?;\n]{{0,60}}\b(?:is|are|remain)\b[^.!?;\n]{{0,30}}\b{_EQUIVALENT}\b"
        rf"|\b(?:the\s+)?{_CAPABILITY_OBJECT}\s+(?:in|of)\s+(?:one|either)\s+{_LANE}\b"
        rf"[^.!?;\n]{{0,80}}\b(?:equals?|matches?|is\s+(?:the\s+same\s+as|identical\s+to|equivalent\s+to))\b"
        rf"[^.!?;\n]{{0,80}}\b(?:the\s+)?(?:set\s+)?(?:supported\s+)?commands?\s+(?:in|of)\s+(?:the\s+)?other\s+{_LANE}\b"
        rf"|\b(?:(?:their|the)\s+)?{_CAPABILITY_OBJECT}\b[^.!?;\n]{{0,60}}"
        rf"\b(?:coincide(?:s)?|match(?:es)?|(?:completely|fully)\s+overlap(?:s)?)\b"
        rf"[^.!?;\n]{{0,80}}\b(?:across|between)\s+(?:the\s+two|both)\s+{_LANES}\b"
        rf"|\b{_CAPABILITY_COMPLEMENT_EQUIV}\b",
        re.I,
    ),
    # Explicit equality of the command set supported by one lane and the other.
    re.compile(
        rf"\b(?:the\s+)?set\s+of\s+commands?\s+(?:supported|available|accepted)\s+(?:by|in)\s+(?:one|either)\s+{_LANE}\b"
        rf"[^.!?;\n]{{0,80}}\b(?:equals?|matches?|is\s+(?:the\s+same\s+as|identical\s+to|equivalent\s+to))\b"
        rf"[^.!?;\n]{{0,80}}\b(?:the\s+)?set(?:\s+of\s+commands?)?\s+(?:supported|available|accepted)\s+(?:by|in)\s+(?:the\s+)?other\s+{_LANE}\b"
        rf"|\bcommands?\s+(?:supported|available|accepted)\s+(?:by|in)\s+(?:one|either)\s+{_LANE}\b"
        rf"[^.!?;\n]{{0,80}}\b(?:are|remain)\s+(?:exactly\s+)?(?:the\s+same|identical|equal)\s+as\b"
        rf"[^.!?;\n]{{0,80}}\b(?:commands?\s+)?(?:supported|available|accepted)\s+(?:by|in)\s+(?:the\s+)?other\s+{_LANE}\b",
        re.I,
    ),
    # Bidirectional command availability collapses the lane capability sets.
    re.compile(
        rf"\b(?:any|every)\s+command\b[^.!?;\n]{{0,50}}\b(?:supported|available|accepted|allowed|exposed|provided)\b"
        rf"[^.!?;\n]{{0,50}}\bin\s+(?:one|either)\s+{_LANE}\b[^.!?;\n]{{0,100}}"
        rf"\b(?:also\s+)?(?:supported|available|accepted|allowed|exposed|provided)\b"
        rf"[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?other\s+{_LANE}\b"
        rf"|\b(?:the\s+two|both)\s+{_LANES}\b[^.!?;\n]{{0,80}}\b(?:support|accept|allow|expose|provide)\b"
        rf"[^.!?;\n]{{0,40}}\beach\s+other['’]s\s+commands\b"
        rf"|\beach\s+{_LANE}\b[^.!?;\n]{{0,60}}\b(?:support|accept|allow|expose|provide)s?\b"
        rf"[^.!?;\n]{{0,40}}\b(?:all|every)\s+(?:command|commands)\b[^.!?;\n]{{0,50}}\b(?:supported|available|accepted|allowed|exposed|provided)\b"
        rf"[^.!?;\n]{{0,30}}\bby\s+(?:the\s+)?other\s+{_LANE}\b",
        re.I,
    ),
    # Nominal/existential lane-equivalence relations tied to command execution.
    re.compile(
        rf"\b(?:there\s+(?:is|exists)\s+(?:an?\s+)?{_RELATION_NOUN}\s+between\s+(?:the\s+two|both)\s+{_LANES}"
        rf"|(?:the\s+two|both)\s+{_LANES}\s+(?:have|share|show|exhibit|possess)\s+(?:an?\s+)?{_RELATION_NOUN}"
        rf"|{_RELATION_NOUN}\s+(?:exists|holds|applies)\s+between\s+(?:the\s+two|both)\s+{_LANES})\b"
        rf"[^.!?;\n]{{0,100}}\b(?:for|in|with\s+respect\s+to)\s+{_COMMAND}\b",
        re.I,
    ),
    re.compile(
        rf"\b{_COMMAND}\b[^.!?;\n]{{0,60}}\b(?:has|shows|exhibits|maintains)\s+(?:an?\s+)?{_RELATION_NOUN}\b"
        rf"[^.!?;\n]{{0,80}}\b(?:across|between)\s+(?:the\s+two|both)\s+{_LANES}\b",
        re.I,
    ),
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


def _relation_is_assertive(text: str, match: re.Match[str]) -> bool:
    """Evaluate polarity at the actual equivalence predicate, not unrelated sentence negation."""
    local = match.group(0)
    reciprocal_text = match.groupdict().get("reciprocal")
    if reciprocal_text is not None:
        reciprocal_start = match.start("reciprocal")
        reciprocal_end = match.end("reciprocal")
        if not occurrence_is_assertive_polarity(text, reciprocal_start, reciprocal_end):
            return False
        reciprocal_suffix = text[reciprocal_end:min(len(text), reciprocal_end + 80)]
        if _RECIPROCAL_REJECTION_AFTER.match(reciprocal_suffix):
            return False
        return True
    markers = list(_RELATION_MARKER.finditer(local))
    if not markers:
        return occurrence_is_assertive_polarity(text, match.start(), match.end())
    relation = markers[-1]
    return occurrence_is_assertive_polarity(
        text,
        match.start() + relation.start(),
        match.start() + relation.end(),
    )


def has_affirmative_cross_lane_equivalence(text: str) -> bool:
    return any(
        _relation_is_assertive(text, match)
        for pattern in _PATTERNS
        for match in pattern.finditer(text)
    )
