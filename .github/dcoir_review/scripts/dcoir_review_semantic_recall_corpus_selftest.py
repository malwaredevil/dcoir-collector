#!/usr/bin/env python3
"""Structural regression checks for the generalized DCOIR semantic recall corpus."""

from __future__ import annotations

import json
from pathlib import Path


CORPUS = Path('.github/dcoir_review/evaluation/semantic_recall_corpus_v1.json')
REQUIRED_FINDING_CLASSES = {
    'polarity-negation',
    'polarity-rejected-proposition',
    'polarity-quotation',
    'scope-binding',
    'lane-wrapper-confusion',
    'polarity-postposed-rejection',
    'representation-duplicate',
    'representation-serialization',
    'mode-scope',
    'actionability-token-cooccurrence',
}
REQUIRED_CLEAN_CLASSES = {
    'precision-valid-membership-expression',
    'precision-documentation-only',
}


def main() -> None:
    data = json.loads(CORPUS.read_text(encoding='utf-8'))
    assert data['schema_version'] == 'dcoir_review_semantic_recall_corpus_v1'
    cases = data.get('cases')
    assert isinstance(cases, list) and len(cases) >= 12

    ids: set[str] = set()
    finding_classes: set[str] = set()
    clean_classes: set[str] = set()
    for case in cases:
        assert isinstance(case, dict)
        case_id = str(case.get('id', '')).strip()
        expected = str(case.get('expected', '')).strip()
        defect_class = str(case.get('defect_class', '')).strip()
        source = str(case.get('source', '')).strip()
        counterexample = str(case.get('counterexample', '')).strip()
        contract = str(case.get('review_contract', '')).strip()
        assert case_id and case_id not in ids
        ids.add(case_id)
        assert expected in {'finding', 'clean'}
        assert defect_class and source and counterexample and contract
        if expected == 'finding':
            finding_classes.add(defect_class)
        else:
            clean_classes.add(defect_class)

    assert REQUIRED_FINDING_CLASSES <= finding_classes
    assert REQUIRED_CLEAN_CLASSES <= clean_classes

    # A finding case must actually exercise the defective implementation as
    # written. Keep the scope-binding counterexample case-compatible with the
    # implementation's case-sensitive token checks so reviewer quality, rather
    # than a broken fixture, determines the disposition.
    scope_case = next(case for case in cases if case['id'] == 'wrong-clause-scope-binding')
    scope_namespace: dict[str, object] = {}
    exec(str(scope_case['source']), scope_namespace)
    assert scope_namespace['has_remote_action'](str(scope_case['counterexample'])) is True
    assert str(scope_case['counterexample']).startswith('remote ')

    # Keep the corpus generalized. It may encode the semantic defect family, but
    # it must not become a lookup table for a specific acceptance PR or issue.
    serialized = json.dumps(data, sort_keys=True).lower()
    for forbidden in ('pull request #448', 'pr #448', 'issue #456', 'gemini_behavioral_replay_scoring.py'):
        assert forbidden not in serialized

    print(
        'dcoir_review_semantic_recall_corpus_selftest passed: '
        f'{len(cases)} cases, {len(finding_classes)} finding classes, {len(clean_classes)} clean classes'
    )


if __name__ == '__main__':
    main()
