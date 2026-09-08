from pathlib import Path

SOURCE_PATH = Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py")
VALIDATOR_PATH = Path("project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


source = SOURCE_PATH.read_text(encoding="utf-8")
validator = VALIDATOR_PATH.read_text(encoding="utf-8")

old = '''def _occurrence_has_direct_shared_context_negation(
    text: str,
    start: int,
) -> bool:
    prefix = text[max(0, start - 180):start]
    direct_use = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:use|share)\\s+(?:the\\s+)?$",
        prefix,
    )
    if direct_use:
        return True

    scoped_action = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:run|execute|place|put|mix|combine)\\b[^.!?;]{0,150}$",
        prefix,
    )
    if not scoped_action:
        return False
    scope = prefix[scoped_action.start():]
    return bool(
        (_clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope))
        or re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", scope)
    )
'''
new = '''def _shared_context_trailing_lane_relation(
    text: str,
    end: int,
    leading_scope: str,
) -> bool:
    suffix = text[end:min(len(text), end + 140)]
    terminator = re.search(r"[.!?;]", suffix)
    if terminator:
        suffix = suffix[:terminator.start()]
    relation = re.match(
        r"^\\s+(?:as|with)\\s+(?:the\\s+)?(?P<target>.+?)\\s*$",
        suffix,
    )
    if not relation:
        return False
    target = relation.group("target")
    leading_endpoint = _clause_has_endpoint_lane(leading_scope)
    leading_local = _clause_has_local_lane(leading_scope)
    target_endpoint = _clause_has_endpoint_lane(target)
    target_local = _clause_has_local_lane(target)
    return bool(
        (leading_endpoint and target_local)
        or (leading_local and target_endpoint)
    )


def _occurrence_has_direct_shared_context_negation(
    text: str,
    start: int,
    end: int,
) -> bool:
    prefix = text[max(0, start - 180):start]
    direct_use = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:use|share)\\s+(?:the\\s+)?$",
        prefix,
    )
    if direct_use:
        return True

    scoped_action = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:run|execute|place|put|mix|combine)\\b[^.!?;]{0,150}$",
        prefix,
    )
    if not scoped_action:
        return False
    scope = prefix[scoped_action.start():]
    if (
        (_clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope))
        or re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", scope)
    ):
        return True
    return _shared_context_trailing_lane_relation(text, end, scope)
'''
source = replace_once(source, old, new, "shared-context negation implementation")

old = '''        if _occurrence_has_direct_shared_context_negation(text, occurrence.start()):
            continue
'''
new = '''        if _occurrence_has_direct_shared_context_negation(
            text, occurrence.start(), occurrence.end()
        ):
            continue
'''
source = replace_once(source, old, new, "assertive shared-context negation call")

old = '''            if _occurrence_has_direct_shared_context_negation(
                segment,
                occurrence.start(),
            ):
                return True
'''
new = '''            if _occurrence_has_direct_shared_context_negation(
                segment,
                occurrence.start(),
                occurrence.end(),
            ):
                return True
'''
source = replace_once(source, old, new, "negated shared-context call")

old = '''        ["do not mix", "don't mix", "dont mix", "must not mix", "should not mix"],
'''
new = '''        [
            "do not mix",
            "don't mix",
            "dont mix",
            "must not mix",
            "should not mix",
            "do not combine",
            "don't combine",
            "dont combine",
            "must not combine",
            "should not combine",
        ],
'''
source = replace_once(source, old, new, "positive no-mix term list")

old = '''def _segment_has_relational_lane_separation(segment: str) -> bool:
'''
new = '''def _occurrence_has_lane_relation_rejection(text: str, start: int) -> bool:
    prefix = text[max(0, start - 160):start]
    return bool(
        re.search(
            r"\\b(?:wrong|incorrect|false|misleading)\\s+to\\s+(?:say|claim)\\b"
            r"[^.!?;]{0,140}$",
            prefix,
        )
    )


def _segment_has_relational_lane_separation(segment: str) -> bool:
'''
source = replace_once(source, old, new, "lane-relation rejection helper insertion")

old = '''    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if _separate_occurrence_targets_lane(segment, occurrence):
            return True
'''
new = '''    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if _occurrence_has_lane_relation_rejection(segment, occurrence.start()):
            continue
        if _separate_occurrence_targets_lane(segment, occurrence):
            return True
'''
source = replace_once(source, old, new, "separate relation rejection guard")

old = '''    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not mix these two lanes.",
        True,
        "response-scope no-mix relationship",
    )
'''
new = old + '''    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not combine these two lanes.",
        True,
        "response-scope no-combine relationship",
    )
'''
validator = replace_once(validator, old, new, "no-combine regression")

old = '''    _expect(
        "It is wrong to say do not mix endpoint response-action syntax and local "
        "workstation PowerShell.",
        False,
        "rejected no-mix assertion",
    )
'''
new = old + '''    _expect(
        "It is wrong to say endpoint response-action commands are separate from local "
        "workstation PowerShell.",
        False,
        "rejected separation assertion",
    )
    _expect(
        "It would be misleading to say endpoint response-action commands are separate "
        "from local workstation PowerShell.",
        False,
        "misleading separation assertion",
    )
'''
validator = replace_once(validator, old, new, "rejected-separation regressions")

old = '''    _expect(
        "Do not run endpoint response-action commands and local workstation PowerShell "
        "in the same shell.",
        True,
        "negated shared-shell relation",
    )
'''
new = old + '''    _expect(
        "Do not run endpoint response-action commands in the same shell as local "
        "workstation PowerShell.",
        True,
        "trailing-lane shared-shell negation",
    )
    _expect(
        "Do not run local workstation PowerShell in the same shell as endpoint "
        "response-action commands.",
        True,
        "trailing-endpoint shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell, and local "
        "workstation PowerShell runs the collector directly.",
        False,
        "unbound trailing lane does not imply separation",
    )
'''
validator = replace_once(validator, old, new, "shared-shell ordering regressions")

SOURCE_PATH.write_text(source, encoding="utf-8")
VALIDATOR_PATH.write_text(validator, encoding="utf-8")
print("Applied issue #484 DCOIR finding fixes to the two intended Python files.")
