from __future__ import annotations

import re

from .gemini_behavioral_replay_assertion_polarity import prefix_has_affirming_negated_truth_frame
from .gemini_behavioral_replay_rejection_patterns import NEGATION_PATTERN, REJECTED_ASSERTION_PATTERN


def occurrence_is_contextually_negated(text: str, start: int) -> bool:
    wide = re.sub(r"[*_]+", "", text[max(0, start - 120):start])
    if prefix_has_affirming_negated_truth_frame(wide):
        return False
    context = wide[-40:]
    return bool(NEGATION_PATTERN.search(context) or REJECTED_ASSERTION_PATTERN.search(context))
