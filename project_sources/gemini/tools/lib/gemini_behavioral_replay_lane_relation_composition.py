"""Compositional endpoint/local lane-relation grammar.

Lane references, relation predicates, and directional command containment are
composed per contrast-free clause instead of enumerating whole sentences, so
paraphrases of lane identity, shared command capability, endpoint-to-local
execution, and reciprocal containment across sentences share one owner. Every
relation is gated by assertion polarity at its predicate.
"""
from __future__ import annotations

import re
from typing import Iterator, Set, Tuple

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_assertive_polarity

_A = r"(?:elastic\s+)?(?:endpoint\s+response\s+console|endpoint\s+console|response\s+console|endpoint\s+response[- ]actions?|response[- ]actions?|endpoint\s+lane)"
_B = r"(?:local\s+(?:workstation\s+)?powershell|workstation\s+powershell|local\s+(?:shell|lane))"
_LANE = {"a": _A, "b": _B}
_TAIL = r"(?:\s+(?:console|commands?|syntax|lane|shell|sessions?))?"
_GROUP = r"(?:(?:both|the\s+two|these|those|the)\s+(?:execution\s+)?(?:lanes|consoles|shells|execution\s+contexts)|(?:either|each)\s+(?:execution\s+)?(?:lane|console|shell))"
_PAIR = rf"(?:(?:the\s+)?{_A}{_TAIL}\s+(?:and|or)\s+(?:the\s+)?{_B}{_TAIL}|(?:the\s+)?{_B}{_TAIL}\s+(?:and|or)\s+(?:the\s+)?{_A}{_TAIL}|{_GROUP})"
_CMD = r"(?:commands?|cmdlets?|syntax(?:es)?|command\s+(?:sets?|vocabular(?:y|ies)|languages?|capabilit(?:y|ies)|inventor(?:y|ies)|repertoires?))"
_ADV = r"(?:(?:just|exactly|basically|essentially|effectively|functionally|simply|merely|really|fully|completely|entirely|practically|also|still|all)\s+)*"
_SAME = r"(?:the\s+same|identical|equal|equivalent|matching|shared|common|interchangeable|mutual|compatible|portable|no\s+different|alike)"
_IDENTITY = (
    r"(?:the\s+same(?!\s+(?!(?:thing|lane|tool|environment|console|shell|for|in|when|across|to|as|with|everywhere)\b)[a-z])|"
    r"one\s+and\s+the\s+same|identical|equivalent|"
    r"interchangeable|substitutable|indistinguishable|synonymous|alike|no\s+different|"
    r"compatible(?!\s+with\s+(?!each\s+other|one\s+another)))"
)
_LIKE = (
    r"(?:the\s+same\s+as|identical\s+to|equivalent\s+to|interchangeable\s+with|substitutable\s+for|"
    r"indistinguishable\s+from|no\s+different\s+(?:from|than)|(?:just\s+|exactly\s+)?like|"
    r"an?\s+(?:drop-in\s+)?(?:replacement|substitute|alias|wrapper|front[- ]end|proxy)\s+(?:for|of|around)|"
    r"nothing\s+(?:more|other)\s+than|an?\s+(?:remote\s+)?)"
)
_COPULA = r"(?:is|are|remains?|seems?|appears?\s+to\s+be|(?:may|might|could|can|would|will)\s+be|acts?\s+as|operates?\s+as|behaves?|works?|functions?)"
_EXEC = r"(?:runs?|run|work|works|execute[sd]?|functions?|pasted|used|accepted|supported|understood|recognized|handled|valid|usable|allowed)"
_TAKE = r"(?:runs?|accepts?|supports?|executes?|understands?|handles?|recognizes?|parses?|takes?)"
_GAP = r"(?:\s+(?:can|could|may|might|will|would|should|must|also|all|both|just|still|then|not|never|cannot|can't|won't|don't|doesn't|do|does|be|are|is|fine|directly|equally|as\s+well|(?!only\b)[a-z]+ly)){0,4}"
_A_CMD = r"(?:elastic\s+)?(?:endpoint\s+)?(?:response[- ]action|response\s+console|endpoint\s+console|endpoint)\s+(?:commands?|syntax(?:es)?|wrappers?)"

# Relations whose group "rel" marks the predicate evaluated for polarity.
_CLAUSE_RELATIONS = tuple(re.compile(pattern, re.I) for pattern in (
    # Lane identity: the pair (or one lane relative to the other) is the same lane.
    rf"\b{_PAIR}\s+(?P<rel>{_COPULA}\s+{_ADV}{_IDENTITY})\b",
    rf"\b(?:the\s+)?{_A}{_TAIL}\s+(?P<rel>{_COPULA}\s+{_ADV}{_LIKE})\s*(?:the\s+)?{_B}\b",
    rf"\b(?:the\s+)?{_B}{_TAIL}\s+(?P<rel>{_COPULA}\s+{_ADV}{_LIKE})\s*(?:the\s+)?{_A}\b(?![-'’])",
    rf"\b(?:the\s+)?(?:{_A}{_TAIL}\s+(?P<rel>(?:is|are|remains?)\s+{_ADV})(?:the\s+)?{_B}|{_B}{_TAIL}\s+(?P<rel2>(?:is|are|remains?)\s+{_ADV})(?:the\s+)?{_A})(?!['’-])\b",
    rf"(?:{_A}|{_B})['’]s\s+{_CMD}\s+(?P<rel>(?:are|is)\s+{_ADV})(?:the\s+same\s+as\s+)?(?:the\s+)?(?:{_A}|{_B})['’]s",
    rf"(?:{_A}|{_B})[^.!?;\n]{{0,60}}\b(?P<rel>(?:the\s+)?same\s+{_CMD}\s+as|(?:identical|equivalent|matching)\s+{_CMD}\s+(?:to|as|with)|{_CMD}\s+(?:identical|equivalent)\s+to)\s+(?:the\s+)?(?:{_A}|{_B})",
    rf"\b(?:{_A}|{_B}){_TAIL}{_GAP}\s+{_TAKE}\s+(?P<rel>(?:exactly|precisely)\s+(?:the\s+)?(?:same\s+)?{_CMD})\s+(?:that\s+|which\s+)?(?:the\s+)?(?:{_A}|{_B})",
    # Shared command capability over the pair, a lane group, or an either/whether alternative.
    rf"\b{_PAIR}\b[^.!?;\n]{{0,60}}?\b(?P<rel>(?:have|has|share|support|accept|use|expose|offer|run)s?\s+{_ADV}(?:(?:exactly|precisely)\s+)?{_SAME}\s+(?:(?:set|sets)\s+of\s+)?(?:supported\s+|available\s+|accepted\s+)?{_CMD})",
    rf"\b{_PAIR}\b[^.!?;\n]{{0,40}}?\b(?P<rel>share\s+(?:(?:one|a|the|a\s+single|the\s+same|their)\s+)?(?:\w+\s+)?{_CMD})\b",
    rf"^(?=[^.!?;\n]*\b(?:{_A}|{_B}|lanes|consoles|shells|either|both)\b)[^.!?;\n]*?\b{_CMD}(?:\s+\w+){{0,2}}?\s+(?P<rel>(?:are|is|remain|stay)s?\s+{_ADV}{_SAME}|(?:work|run|behave|execute|function|perform)s?\s+{_ADV}(?:the\s+same|identically|equally|equivalently|alike|interchangeably)|in\s+common)\b"
    rf"(?=\s*(?:$|[,.;:!?])|[^.!?;\n]{{0,80}}?(?:{_A}[^.!?;\n]{{0,60}}?{_B}|{_B}[^.!?;\n]{{0,60}}?{_A}|\b{_GROUP}\b|\bwith\s+each\s+other\b))",
    rf"\b{_CMD}(?:\s+\w+){{0,3}}?\s+(?P<rel>(?:work|run|execute|function)s?\s+{_ADV}(?:in|on|from|across)\s+(?:both|either)\s+(?:execution\s+)?(?:lanes?|consoles?|shells?|environments?))\b",
    rf"\b(?P<rel>(?:either|both)\s+(?:execution\s+)?(?:lanes?|consoles?|shells?)|either\s+(?:the\s+)?{_A}{_TAIL}\s+or\s+(?:the\s+)?{_B}{_TAIL}|either\s+(?:the\s+)?{_B}{_TAIL}\s+or\s+(?:the\s+)?{_A}{_TAIL})\s+(?:will\s+|can\s+|would\s+|could\s+)?{_TAKE}\s+(?:any|all|every|these|those|the\s+same)\b[^.!?;\n]{{0,30}}\b{_CMD}",
    rf"\b(?P<rel>(?:use|pick|choose)\s+(?:either|any)\s+(?:execution\s+)?(?:lane|console|shell))\s+for\s+(?:any|all|every|these|those|the\s+same)\b[^.!?;\n]{{0,20}}\b{_CMD}",
    rf"\b(?:{_A}|{_B}){_TAIL}\s+(?P<rel>mirrors?|duplicates?|replicates?|matches)\s+(?:the\s+)?(?:{_A}|{_B})(?:['’]s)?(?:\s+\w+){{0,2}}\s+{_CMD}",
    rf"\b(?P<rel>(?:no|zero)\s+(?:real\s+|meaningful\s+|practical\s+)?(?:difference|distinction)|(?:does|do)\s*(?:not|n['’]t)\s+matter|makes?\s+no\s+difference)\b[^.!?;\n]{{0,80}}(?:{_A}[^.!?;\n]{{0,60}}\b(?:or|and)\b[^.!?;\n]{{0,20}}{_B}|{_B}[^.!?;\n]{{0,60}}\b(?:or|and)\b[^.!?;\n]{{0,20}}{_A})",
    rf"(?:{_PAIR}|{_A}[^.!?;\n]{{0,60}}{_B}|{_B}[^.!?;\n]{{0,60}}{_A})[^.!?;\n]{{0,60}}\b(?P<rel>interchangeabl[ey])",
    rf"(?:{_A}|{_B})[^.!?;\n]{{0,60}}\b(?P<rel>interchangeabl[ey])\s+(?:with|to)\s+(?:the\s+)?(?:{_A}|{_B})",
    rf"\b(?P<rel>(?:swap|interchange|substitute)\s+(?:the\s+)?(?:{_A}|{_B}){_TAIL}\s+(?:for|with|and)\s+(?:the\s+)?(?:{_A}|{_B}){_TAIL})\s+(?:freely|whenever|at\s+will|as\s+(?:needed|you\s+(?:like|wish|prefer))|any\s*time|either\s+way)",
    # Inverse containment wording: one lane contains the other's command set.
    rf"\b(?:the\s+)?{_B}{_TAIL}\s+(?P<rel>contains?|includes?|covers?)\s+(?:all\s+of\s+)?(?:the\s+)?{_A}(?:['’]s)?\s+(?:command\s+)?(?:sets?|commands)(?:\s+as\s+(?:a\s+)?subset)?\b",
    rf"\b(?:the\s+)?{_A}{_TAIL}\s+(?P<rel>contains?|includes?|covers?)\s+(?:all\s+of\s+)?(?:the\s+)?{_B}(?:['’]s)?\s+(?:command\s+)?(?:sets?|commands)(?:\s+as\s+(?:a\s+)?subset)?\b",
    # Blanket one-way containment is also a lane-boundary violation. The two
    # lanes can wrap/transport a shell payload explicitly, but neither lane's
    # command vocabulary is a general subset of the other.
    r"\b(?:every|all|any)\s+commands?\s+(?:supported|available|accepted|allowed|exposed|provided)\s+(?:by|in)\s+(?:one|either)\s+(?:console|shell|environment|execution\s+lane)\s+(?P<rel>(?:is|are)\s+(?:also\s+)?(?:supported|available|accepted|allowed|exposed|provided))\s+(?:by|in)\s+(?:the\s+)?other(?:\s+(?:console|shell|environment|execution\s+lane))?\b",
    rf"\b(?:every|all|any)\s+commands?\s+(?:supported|available|accepted|allowed|exposed|provided)\s+(?:by|in)\s+(?:the\s+)?{_A}{_TAIL}\s+(?P<rel>(?:is|are)\s+(?:also\s+)?(?:supported|available|accepted|allowed|exposed|provided))\s+locally\b",
    # Double-negative equivalence: no command separates the lanes.
    r"\b(?P<rel>neither\s+(?:execution\s+)?(?:lane|console|shell)\s+lacks)\b[^.!?;\n]{0,40}\bthe\s+other",
    r"\b(?P<rel>(?:each|either)\s+(?:execution\s+)?(?:lane|console|shell)['’]s\s+command\s+sets?\s+(?:contains|includes|covers|equals|matches))\s+the\s+other",
    # One-way endpoint response-action execution in the local lane.
    rf"\b{_A_CMD}{_GAP}\s+(?P<rel>{_EXEC})(?:\s+(?!(?:not|never|only|but|and|or|except|instead|rather|than)\b)[a-z-]+){{0,2}}?\s+(?:in|into|from|on|inside|within|via|through|by|with)\s+(?:the\s+|a\s+)?{_B}\b"
    rf"(?![^.!?;\n]{{0,40}}\b(?:fail(?:s|ed)?|errors?|break(?:s)?|throw(?:s)?|won't|will\s+not|cannot|can't|(?:do|does)\s*(?:not|n't)|(?:is|are)\s+(?:rejected|invalid|unsupported))\b)",
    rf"\b{_B}{_TAIL}{_GAP}\s+(?P<rel>{_TAKE})\s+(?:the\s+|all\s+|any\s+|every\s+)?{_A_CMD}",
))

# Sentence-scoped: the contrast inside these double negatives must not split the clause.
_SENTENCE_RELATIONS = (re.compile(
    rf"\b(?P<rel>no\s+commands?)\s+(?:that\s+|which\s+)?(?:\w+\s+){{0,2}}?{_EXEC}[^.!?;\n]{{0,40}}\bone\s+(?:execution\s+)?(?:lane|console|shell)\b"
    rf"[^.!?;\n]{{0,30}}\b(?:but|and|yet)\b[^.!?;\n]{{0,40}}\bthe\s+other", re.I),)

_CONTRAST_SPLIT = re.compile(r"\b(?:but|however|whereas|while|although|though|yet|except|unlike|instead|rather\s+than)\b", re.I)
_SENTENCE = re.compile(r"[^.!?;\n]+[.!?;\n]?")


def _ref(lane: str) -> str:
    return rf"(?:the\s+)?{_LANE[lane]}"


def _containment_patterns(src: str, dst: str) -> Tuple[re.Pattern[str], ...]:
    """Assertions that every command of lane ``src`` is available in lane ``dst``."""
    s, d = _ref(src), _ref(dst)
    s_cmd = rf"{s}(?:['’]s)?\s+{_CMD}"
    return tuple(re.compile(pattern, re.I) for pattern in (
        rf"\b(?:every|all|any|each)\s+(?:of\s+the\s+)?{s_cmd}\s+(?P<rel>(?:is|are)\s+{_ADV}(?:an?\s+)?(?:valid\s+|supported\s+)?){d}",
        rf"\b{d}{_TAIL}\s+(?P<rel>(?:also\s+|likewise\s+|similarly\s+|equally\s+)?{_TAKE})\s+(?:every|all|any|each)\s+(?:of\s+the\s+)?{s_cmd}",
        rf"\b{d}{_TAIL}\s+(?P<rel>(?:also\s+|likewise\s+|similarly\s+|equally\s+)?{_TAKE})\s+(?:every|all|any|each)\s+(?:of\s+the\s+)?(?:commands?|syntax)\s+(?:that\s+)?{s}{_TAIL}\s+(?:{_TAKE}|does)\b",
        rf"\b(?:every|all|any)\s+commands?\s+(?:supported|available|accepted)\s+(?:by|in)\s+{s}{_TAIL}\s+(?P<rel>(?:is|are)\s+(?:also\s+)?(?:supported|available|accepted))\s+(?:by|in)\s+{d}",
        rf"\b(?:what|whatever|anything)\s+(?:works|runs|executes)\s+in\s+{s}{_TAIL}\s+(?P<rel>(?:also\s+)?(?:works|runs|executes))\s+in\s+{d}",
        rf"\b{s}(?:['’]s)?(?:\s+(?:command\s+)?(?:sets?|commands))?\s+(?P<rel>(?:is|are)\s+(?:a\s+)?(?:subset|contained)\s+(?:of|in))\s+{d}",
        rf"\b{d}(?:['’]s)?(?:\s+(?:command\s+)?(?:sets?|commands))?\s+(?P<rel>(?:is|are)\s+(?:a\s+)?superset\s+of)\s+{s}",
        rf"\b{d}{_TAIL}\s+(?P<rel>(?:also\s+|likewise\s+|similarly\s+|equally\s+)?{_TAKE})\s+(?:all\s+(?:of\s+)?)?{s}['’]s(?:\s+{_CMD})?",
        rf"\b{d}{_TAIL}\s+(?P<rel>(?:does|do)\s+(?:(?:so\s+)?too|(?:so\s+)?as\s+well|likewise|the\s+same))\s+for\s+{s}",
    ))


_CONTAINMENT = {("a", "b"): _containment_patterns("a", "b"), ("b", "a"): _containment_patterns("b", "a")}


def _sentences(text: str) -> Iterator[re.Match[str]]:
    for sentence in _SENTENCE.finditer(text):
        if not sentence.group(0).rstrip().endswith("?"):
            yield sentence


def _clauses(text: str) -> Iterator[Tuple[int, str]]:
    for sentence in _sentences(text):
        start = sentence.start()
        cursor = 0
        body = sentence.group(0)
        for split in _CONTRAST_SPLIT.finditer(body):
            yield start + cursor, body[cursor:split.start()]
            cursor = split.end()
        yield start + cursor, body[cursor:]


def _asserted(text: str, offset: int, match: re.Match[str]) -> bool:
    """Require assertion both over the whole relation and at its predicate.

    The whole-relation check sees frames such as "do not assume" that a
    coordinated subject ("A and B are ...") would hide from the predicate; the
    predicate check sees negation between subject and verb ("cannot be run").
    """
    group = "rel" if match.group("rel") is not None else "rel2"
    start, end = offset + match.start(group), offset + match.end(group)
    return occurrence_is_assertive_polarity(text, offset + match.start(), end) and occurrence_is_assertive_polarity(text, start, end)


def has_composed_lane_equivalence(text: str) -> bool:
    for sentence in _sentences(text):
        for pattern in _SENTENCE_RELATIONS:
            if any(_asserted(text, sentence.start(), match) for match in pattern.finditer(sentence.group(0))):
                return True
    directions: Set[Tuple[str, str]] = set()
    for offset, clause in _clauses(text):
        for pattern in _CLAUSE_RELATIONS:
            if any(_asserted(text, offset, match) for match in pattern.finditer(clause)):
                return True
        for direction, patterns in _CONTAINMENT.items():
            if any(_asserted(text, offset, match) for pattern in patterns for match in pattern.finditer(clause)):
                directions.add(direction)
    # Any blanket command-set containment across the endpoint and local lanes
    # collapses the governed syntax boundary. A response action may explicitly
    # wrap a PowerShell payload, but that does not make either lane's command
    # set a subset/superset of the other.
    return bool(directions)
