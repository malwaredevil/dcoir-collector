"""Truth-frame grammar: negated doubt/denial frames that affirm their complement.

A negator that attaches to an epistemic-rejection word ("no question", "not in
dispute", "no one doubts", "I do not question") cancels that rejection, so the
complement it introduces is asserted. Every polarity layer consults this one
grammar so the frames stay consistent across scorers.
"""
from __future__ import annotations

import re

TRUTH_FRAME_MODIFIER = (
    r"(?:remotely|seriously|reasonably|credibly|genuinely|meaningfully|materially|substantially|"
    r"particularly|especially|really|even|at\s+all|in\s+the\s+least|"
    r"in\s+any\s+(?:(?:meaningful|material|reasonable|credible|serious)\s+)?(?:way|sense|degree)|"
    r"in\s+the\s+slightest(?:\s+degree)?|by\s+any\s+means)"
)

_MOD = rf"(?:(?:{TRUTH_FRAME_MODIFIER})\s+){{0,3}}"
_WORD = r"(?:(?:[a-z][a-z-]{1,24})\s+)"
_ADVERB = r"(?:(?:[a-z][a-z-]{1,24}ly|in\s+good\s+faith|in\s+any\s+(?:reasonable|serious|credible)\s+sense)\s+)"
_IT_BE = r"(?:(?:it\s+(?:is|was|has\s+been|had\s+been|will\s+be|remains)|it['’]s)\s+)?"
_NEG = rf"(?:not|never|by\s+no\s+means)\s+{_MOD}"
# Doubt vocabulary. "arguable" is deliberately absent: "not arguable that X" rejects X.
_DOUBT_STATE = (
    r"(?:doubtful|questionable|uncertain|debatable|disputable|deniable|contestable|controversial|"
    r"in\s+(?:doubt|dispute|question)|open\s+to\s+(?:(?:any|the)\s+)?"
    r"(?:(?:serious|reasonable|credible|real|meaningful|material|substantial|slightest)\s+)?"
    r"(?:doubt|question|dispute|debate))"
)
_DOUBT_NOUN = r"(?:disputes?|doubts?|questions?|debates?|controvers(?:y|ies)|uncertaint(?:y|ies))"
_DOUBT_VERB = r"(?:deny|dispute|doubt|question|reject|refute|contest|contradict)"
_DOUBT_VERB_FINITE = (
    r"(?:denies|denied|disputes|disputed|doubts|doubted|questions|questioned|rejects|rejected|"
    r"refutes|refuted|contests|contested|contradicts|contradicted)"
)
_DOUBT_PARTICIPLE = r"(?:denied|disputed|doubted|questioned|rejected|refuted|contested|contradicted)"
_DOUBT_GERUND = r"(?:denying|disputing|doubting|questioning|rejecting|refuting|contesting|contradicting)"
_PROPOSITION = r"(?:(?:(?:about|over)\s+)?(?:the\s+)?(?:fact|claim|assertion|proposition)\s+)?"
_THERE = (
    r"there(?:['’]s|\s+(?:is|are|was|were|remains?|(?:has|have|had)\s+been|"
    r"(?:can|could|would|should|may|might|will)\s+be))"
)
_THERE_NEVER = r"there(?:['’]s|\s+(?:is|are|was|were|has|have|had))\s+never(?:\s+been)?"
_THERE_NOT = (
    r"there\s+(?:cannot|can't|can\s+not|could\s+not|couldn't|would\s+not|wouldn't|should\s+not|"
    r"shouldn't|must\s+not|mustn't|is\s+not|isn't|are\s+not|aren't|was\s+not|wasn't|were\s+not|"
    r"weren't|(?:has|have|had)\s+not|hasn't|haven't|hadn't)"
)
_NOBODY = (
    r"(?:no\s+one|nobody|not\s+one(?:\s+[a-z0-9_-]+){0,3}|not\s+a\s+single(?:\s+[a-z0-9_-]+){0,3}|"
    r"no(?:\s+[a-z0-9_-]+){1,5})"
)
_NEG_AUX = (
    r"(?:(?:do|does|did|can|could|would|will|should|must)\s+not|don't|doesn't|didn't|cannot|can't|"
    r"couldn't|wouldn't|won't|shouldn't|mustn't|never)"
)
_NEG_PASSIVE = (
    rf"(?:(?:cannot|can't|can\s+not|could\s+not|couldn't|would\s+not|wouldn't|should\s+not|shouldn't|"
    rf"must\s+not|mustn't)\s+{_ADVERB}{{0,3}}be"
    r"|(?:is|are|was|were)\s+(?:not|never)|isn't|aren't|wasn't|weren't"
    r"|(?:has|have|had)\s+(?:not|never)\s+been|hasn't\s+been|haven't\s+been|hadn't\s+been)"
)
# "there is no doubt these settings ..." may omit "that" before a complement subject.
_BARE_COMPLEMENT = (
    r"(?=\s+(?!(?:about|over|of|as|to|whether|if|regarding|concerning|on|for|in|at|left|remaining|"
    r"here|there|was|is|were|are|has|have|had|remains?|exists?|that)\b)[a-z])"
)

NEGATED_TRUTH_FRAME = re.compile(
    rf"\b{_IT_BE}{_NEG}{_DOUBT_STATE}\s+that\b"
    rf"|\b{_THERE}\s+{_NEG}(?:(?:the\s+)?(?:slightest|least)|any(?:\s+(?:serious|reasonable|credible|material|meaningful))?)?"
    rf"\s*{_DOUBT_NOUN}\s+{_PROPOSITION}that\b"
    rf"|\b{_IT_BE}not\s+(?:false|incorrect|untrue|wrong|inaccurate|unsupported|unproven|unjustified|"
    rf"unsubstantiated|unfounded)\s+that\b"
    rf"|\b{_IT_BE}(?:hardly|scarcely|barely)\s+(?:false|incorrect|untrue|wrong|inaccurate)\s+that\b"
    rf"|\b{_THERE}\s+no\s+reason\s+to\s+{_DOUBT_VERB}\s+that\b"
    rf"|\b{_THERE}\s+no\s+{_WORD}{{0,3}}{_DOUBT_NOUN}(?:\s+{_PROPOSITION}that\b|{_BARE_COMPLEMENT})"
    rf"|\b{_THERE_NOT}\s+{_ADVERB}{{0,2}}(?:be(?:en)?\s+)?(?:any|an?|one)\s+{_WORD}{{0,3}}{_DOUBT_NOUN}\s+{_PROPOSITION}that\b"
    rf"|\b{_THERE_NEVER}\s+(?:(?:any|an?|the\s+(?:slightest|least))\s+)?{_WORD}{{0,3}}{_DOUBT_NOUN}\s+{_PROPOSITION}that\b"
    rf"|\b{_THERE}\s+no\s+{_DOUBT_GERUND}\s+(?:(?:the\s+)?(?:fact|claim|assertion|proposition)\s+)?that\b"
    rf"|\b{_THERE}\s+no\s+{_WORD}{{0,3}}(?:room|basis|grounds?|way)\s+(?:(?:for|to)\s+|on\s+which\s+to\s+)"
    rf"{_WORD}{{0,2}}{_DOUBT_VERB}\s+{_PROPOSITION}that\b"
    rf"|\b{_NEG_PASSIVE}\s+{_ADVERB}{{0,3}}{_DOUBT_PARTICIPLE}\s+that\b"
    rf"|\b{_NOBODY}\s+(?:(?:can|could|would|should|may|might|will)\s+)?"
    rf"(?:(?:reasonably|possibly|credibly|seriously|honestly|really|actually|genuinely|even|ever)\s+){{0,2}}"
    rf"(?:{_DOUBT_VERB}|{_DOUBT_VERB_FINITE})\s+{_PROPOSITION}that\b"
    rf"|\b{_NOBODY}\s+(?:has|had)\s+(?:any\s+)?(?:reason|basis|grounds?)\s+to\s+{_DOUBT_VERB}\s+{_PROPOSITION}that\b"
    rf"|\b{_NEG_AUX}\s+(?:(?:[a-z][a-z-]{{1,24}}ly|really|even|ever)\s+){{0,2}}{_DOUBT_VERB}\s+{_PROPOSITION}that\b",
    re.I,
)
