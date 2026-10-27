#!/usr/bin/env python3
"""Independent hostile tests of the canonical two-target Knowledge projection owner."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project_sources/agent_runtime/tools'))
from openai_builder_knowledge_projection import validate_knowledge_projections

TARGETS = (('DCOIR', 'openai_dcoir_analyst', 7), ('USB', 'openai_usb_reporting', 1))
SCHEMA = 'dcoir.agent_runtime.knowledge_projection.target.v1'


def fixture(target):
    return json.loads((ROOT / f'project_sources/agent_runtime/generated/knowledge/{target}/manifest.json').read_text())


def check(root, label, target, count, manifest):
    errors = []
    records = validate_knowledge_projections(root, manifest, errors,
        target_id=target, schema=SCHEMA, expected_count=count, label=label)
    return records, errors


def test_safe_projection_records():
    for label, target, count in TARGETS:
        manifest = fixture(target)
        records, errors = check(ROOT, label, target, count, manifest)
        assert not errors and len(records) == count, (target, errors)
        assert [x['order'] for x in records] == list(range(count))
        for rec, source in zip(records, manifest['projections']):
            assert set(rec) == {'id', 'order', 'path', 'sha256', 'bytes'}
            assert rec['sha256'] == source['sha256'] and rec['bytes'] == source['bytes']


def test_hostile_manifest_shapes_and_drift():
    for label, target, count in TARGETS:
        original = fixture(target)
        variants = (
            ('schema', lambda p: p.__setitem__('schema', 'bad'), 'Unexpected'),
            ('target', lambda p: p.__setitem__('target_id', 'other'), 'wrong target_id'),
            ('list', lambda p: p.__setitem__('projections', 'bad'), 'must be an array'),
            ('extra', lambda p: p['projections'].append(copy.deepcopy(p['projections'][0])), 'Expected'),
            ('order', lambda p: p['projections'][0].__setitem__('order', 99), 'contiguous'),
            ('object', lambda p: p['projections'].__setitem__(0, 'bad'), 'non-object'),
            ('hash', lambda p: p['projections'][0].__setitem__('sha256', '0'*64), 'drift'),
            ('length', lambda p: p['projections'][0].__setitem__('bytes', -1), 'drift'),
            ('absolute', lambda p: p['projections'][0].__setitem__('output_path', '/tmp/escape'), 'absolute'),
            ('traversal', lambda p: p['projections'][0].__setitem__('output_path', chr(46)*2 + '/escape'), 'traversal'),
            ('ceiling', lambda p: p.__setitem__('strict_file_count_ceiling', False), 'ceiling is invalid'),
        )
        for name, mutate, expected in variants:
            altered = copy.deepcopy(original)
            mutate(altered)
            _, errors = check(ROOT, label, target, count, altered)
            assert any(expected in e for e in errors), (target, name, errors)


def test_cross_target_and_symlink_escape_rejected():
    for label, target, count in TARGETS:
        altered = fixture(target)
        other = 'openai_usb_reporting' if label == 'DCOIR' else 'openai_dcoir_analyst'
        altered['projections'][0]['output_path'] = f'project_sources/agent_runtime/generated/knowledge/{other}/manifest.json'
        _, errors = check(ROOT, label, target, count, altered)
        assert any('outside its declared root' in e for e in errors), errors
        with tempfile.TemporaryDirectory(prefix='openai-knowledge-target-') as temp:
            root = Path(temp)
            folder = root / f'project_sources/agent_runtime/generated/knowledge/{target}'
            folder.mkdir(parents=True)
            outside = root / 'outside.txt'
            outside.write_text('sentinel')
            link = folder / 'link.md'
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                continue
            m = fixture(target)
            m['projections'][0]['output_path'] = link.relative_to(root).as_posix()
            _, errors = check(root, label, target, count, m)
            assert any('outside its declared root' in e for e in errors), errors
            assert outside.read_text() == 'sentinel'


def main():
    tests = (test_safe_projection_records, test_hostile_manifest_shapes_and_drift,
             test_cross_target_and_symlink_escape_rejected)
    for case in tests:
        case()
    print(json.dumps({'success': True, 'tests': [t.__name__ for t in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
