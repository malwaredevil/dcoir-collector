#!/usr/bin/env python3
"""Independent hostile, safe and pinned two-target OpenAI behavior snapshot tests."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project_sources/agent_runtime/tools'))
import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb
from openai_builder_behavior_snapshot import validate_behavior_snapshot

TARGETS = (('openai_dcoir_analyst', dcoir), ('openai_usb_reporting', usb))
BASE = Path('project_sources/agent_runtime')


def fixture(target_id: str, builder):
    source = json.loads((ROOT / BASE / 'Shared_Agent_Source_Manifest.json').read_text())
    modules = json.loads((ROOT / BASE / 'Behavior_Module_Manifest.json').read_text())
    adapter = json.loads((ROOT / BASE / f'provider_adapters/{target_id}/Adapter_Manifest.json').read_text())
    return source, modules, adapter


def evaluate(root: Path, builder, source: dict, modules: dict, adapter: dict):
    errors: list[str] = []
    snapshot, digest = validate_behavior_snapshot(
        root, source, modules, adapter['coverage'], errors,
        target_id=builder.TARGET_ID,
        expected_count=builder.EXPECTED_BEHAVIOR_ITEMS,
        instructions_path=builder.EXPECTED_OUTPUTS['instructions'],
        section_headings=builder.SECTION_HEADINGS,
    )
    return snapshot, digest, errors


def test_safe_pinned_snapshot_and_order():
    for target, builder in TARGETS:
        source, modules, adapter = fixture(target, builder)
        records, digest, errors = evaluate(ROOT, builder, source, modules, adapter)
        assert not errors and len(records) == builder.EXPECTED_BEHAVIOR_ITEMS, (target, errors)
        assert digest == adapter['behavior_source_snapshot_sha256'], (target, digest)
        applicable = [item['id'] for item in source['behavior_items'] if target in item.get('applies_to', [])]
        assert [item['id'] for item in records] == applicable
        assert all(set(item)=={'id','source_path','sha256','sections'} for item in records)


def test_hostile_coverage_and_module_mutations_fail_closed():
    for target, builder in TARGETS:
        original = fixture(target, builder)
        applicable_index = next(i for i, item in enumerate(original[0]['behavior_items'])
                                if target in item.get('applies_to', []))
        module_index = next(i for i, module in enumerate(original[1]['modules'])
                            if module.get('id') == original[0]['behavior_items'][applicable_index]['id'])
        scenarios = (
            ('coverage-not-list', lambda s,m,a: a.__setitem__('coverage', None),
             'Adapter coverage must be an array'),
            ('source-not-list', lambda s,m,a: s.__setitem__('behavior_items', None),
             'inventories must be arrays'),
            ('modules-not-list', lambda s,m,a: m.__setitem__('modules', None),
             'inventories must be arrays'),
            ('duplicate-module', lambda s,m,a: m['modules'].append(copy.deepcopy(m['modules'][0])),
             'Duplicate behavior module id'),
            ('nonobject-module', lambda s,m,a: m['modules'].append(None),
             'non-object entry'),
            ('bad-order', lambda s,m,a: a['coverage'].reverse(),
             'coverage must exactly match source-contract order'),
            ('duplicate-coverage', lambda s,m,a: a['coverage'].__setitem__(1, copy.deepcopy(a['coverage'][0])),
             'Duplicate behavior coverage id'),
            ('missing-coverage', lambda s,m,a: a['coverage'].pop(),
             'coverage must exactly match source-contract order'),
            ('empty-sections', lambda s,m,a: a['coverage'][0].__setitem__('sections', []),
             'invalid instruction section coverage'),
            ('unknown-section', lambda s,m,a: a['coverage'][0].__setitem__('sections', ['not-a-section']),
             'invalid instruction section coverage'),
            ('unhashable-section', lambda s,m,a: a['coverage'][0].__setitem__('sections', [[]]),
             'invalid instruction section coverage'),
            ('hash-drift', lambda s,m,a: m['modules'][module_index].__setitem__('sha256', '0'*64),
             'Behavior source hash drift'),
            ('module-path-drift', lambda s,m,a: m['modules'][module_index].__setitem__('source_path', 'wrong.md'),
             'Behavior path disagreement'),
            ('bad-disposition', lambda s,m,a: s['behavior_items'][applicable_index]['target_dispositions'][target].__setitem__('mode', 'invalid'),
             'disposition'),
            ('wrong-owner', lambda s,m,a: s['behavior_items'][applicable_index]['target_dispositions'][target].__setitem__('owner', 'wrong'),
             'disposition owner drift'),
            ('wrong-output', lambda s,m,a: s['behavior_items'][applicable_index]['target_dispositions'][target].__setitem__('generated_output', 'wrong'),
             'disposition output drift'),
            ('nonstring-id', lambda s,m,a: s['behavior_items'][applicable_index].__setitem__('id', []),
             'behavior item id is invalid'),
            ('nonobject-coverage', lambda s,m,a: a['coverage'].__setitem__(0, None),
             'invalid instruction section coverage'),
            ('missing-source-file', lambda s,m,a: s['behavior_items'][applicable_index].__setitem__('source_path', 'missing-source-file.md'),
             'Missing behavior source'),
            ('source-path-traversal', lambda s,m,a: s['behavior_items'][applicable_index].__setitem__('source_path', chr(46)*2+'/source'),
             'traversal'),
        )
        for name, mutate, expected in scenarios:
            source, modules, adapter = copy.deepcopy(original)
            mutate(source, modules, adapter)
            _, _, errors = evaluate(ROOT, builder, source, modules, adapter)
            if name == 'bad-disposition' and target == 'openai_usb_reporting':
                expected = 'must be adapted'
            assert any(expected in error for error in errors), (target, name, errors)


def test_symlinked_behavior_source_cannot_escape_repo():
    for target, builder in TARGETS:
        with tempfile.TemporaryDirectory(prefix='openai-behavior-adva-') as temporary:
            root = Path(temporary)
            staged = root / 'repo'
            folder = staged / BASE / 'behavior_modules'
            folder.mkdir(parents=True)
            outside = root / 'outside.md'
            outside.write_text('untouched', encoding='utf-8')
            link = folder / 'linked.md'
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError):
                continue
            source, modules, adapter = fixture(target, builder)
            item = next(x for x in source['behavior_items'] if target in x.get('applies_to', []))
            item['source_path'] = link.relative_to(staged).as_posix()
            _, _, errors = evaluate(staged, builder, source, modules, adapter)
            assert any('escapes the repository' in x for x in errors), (target, errors)
            assert outside.read_text(encoding='utf-8') == 'untouched'


def main() -> int:
    tests = (test_safe_pinned_snapshot_and_order,
             test_hostile_coverage_and_module_mutations_fail_closed,
             test_symlinked_behavior_source_cannot_escape_repo)
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [x.__name__ for x in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
