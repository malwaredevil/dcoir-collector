#!/usr/bin/env python3
"""Hostile and valid two-target OpenAI source/behavior manifest contract checks."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project_sources/agent_runtime/tools'))
import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb
import openai_builder_validation_kernel as kernel
import openai_builder_behavior_snapshot as behavior_snapshot
import openai_builder_source_contract as source_contract

TARGETS = (('openai_dcoir_analyst', dcoir), ('openai_usb_reporting', usb))
COMMON = (
    'Shared_Agent_Source_Manifest.json',
    'Behavior_Module_Manifest.json',
    'Knowledge_Projection_Manifest.json',
)
BASE = Path('project_sources/agent_runtime')


def stage(target_id: str):
    temporary = tempfile.TemporaryDirectory(prefix='issue605-manifest-')
    repo = Path(temporary.name)
    for filename in COMMON:
        src = ROOT / BASE / filename
        dest = repo / BASE / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    for relative in (
        BASE / 'behavior_modules',
        BASE / f'provider_adapters/{target_id}',
        BASE / f'generated/knowledge/{target_id}',
    ):
        dest = repo / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / relative, dest)
    adapter = repo / BASE / f'provider_adapters/{target_id}/Adapter_Manifest.json'
    return temporary, repo, adapter


def write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run_mutation(target_id, builder, alter, *, target_file='source'):
    tmp, repo, adapter = stage(target_id)
    try:
        config = json.loads(adapter.read_text(encoding='utf-8'))
        source_path = repo / config['source_contract']
        knowledge_target_path = repo / config['knowledge_target_manifest']
        source = json.loads(source_path.read_text(encoding='utf-8'))
        projection_path = repo / config['knowledge_projection_manifest']
        projection = json.loads(projection_path.read_text(encoding='utf-8'))
        behavior_path = repo / config['behavior_module_manifest']
        behavior = json.loads(behavior_path.read_text(encoding='utf-8'))
        if target_file == 'source':
            alter(source)
            write_json(source_path, source)
            knowledge = json.loads(knowledge_target_path.read_text(encoding='utf-8'))
            knowledge['source_contract_sha256'] = hashlib.sha256(source_path.read_bytes()).hexdigest()
            write_json(knowledge_target_path, knowledge)
        elif target_file == 'projection':
            alter(projection)
            write_json(projection_path, projection)
        else:
            alter(behavior)
            write_json(behavior_path, behavior)
        errors, report = builder.build_package(repo, adapter, check=False)
        package = repo / BASE / f'generated/packages/{target_id}'
        return errors, report, package.exists()
    finally:
        tmp.cleanup()


def replace_disposition(source, target_id, item_id, field, value):
    items = source['behavior_items']
    item = next(value for value in items if value['id'] == item_id)
    if field == 'remove':
        item['target_dispositions'].pop(target_id)
    else:
        item['target_dispositions'][target_id][field] = value


def test_source_dispositions_and_modes() -> None:
    scenarios = (
        ('openai_dcoir_analyst', dcoir, 'prime.chunk.00', 'mode', 'flatten', 'expected adapt'),
        ('openai_dcoir_analyst', dcoir, 'sub_agent.01', 'mode', 'adapt', 'expected flatten'),
        ('openai_dcoir_analyst', dcoir, 'sub_agent.01', 'mode', 'exclude', 'expected flatten'),
        ('openai_usb_reporting', usb, 'prime.chunk.00', 'mode', 'flatten', 'must be adapted'),
        ('openai_usb_reporting', usb, 'prime.chunk.00', 'mode', True, 'must be adapted'),
        ('openai_dcoir_analyst', dcoir, 'prime.chunk.00', 'owner', 'not-owner', 'owner drift'),
        ('openai_usb_reporting', usb, 'prime.chunk.00', 'generated_output', 'other', 'output drift'),
        ('openai_dcoir_analyst', dcoir, 'prime.chunk.00', 'remove', None, 'lacks a valid'),
        ('openai_usb_reporting', usb, 'prime.chunk.00', 'remove', None, 'lacks a valid'),
    )
    for target_id, builder, item_id, field, value, expected in scenarios:
        errors, report, wrote = run_mutation(
            target_id, builder,
            lambda source: replace_disposition(source, target_id, item_id, field, value),
        )
        assert any(expected in error for error in errors), (target_id, item_id, field, errors)
        assert report.get('success') is False and not wrote, (target_id, errors, report)


def test_target_uniqueness_and_shape() -> None:
    cases = (
        ('duplicate', lambda src,t:src['targets'].append(dict(next(
            item for item in src['targets'] if item['id'] == t
        ))), 'duplicate'),
        ('missing', lambda src,t:src.__setitem__('targets', [
            item for item in src['targets'] if item.get('id') != t
        ]), 'lacks the'),
        ('nonobject', lambda src,t:src['targets'].append(None), 'non-object'),
        ('not-list', lambda src,t:src.__setitem__('targets', {}), 'must be an array'),
    )
    for target_id, builder in TARGETS:
        for name, mutate, expected in cases:
            errors, report, wrote = run_mutation(
                target_id, builder, lambda src: mutate(src, target_id),
            )
            assert any(expected in error for error in errors), (target_id, name, errors)
            assert report.get('success') is False and not wrote, (target_id,name,report)


def test_projection_binding_shape_and_count() -> None:
    cases = (
        ('not-dict', lambda proj,t:proj.__setitem__('targets', []), 'must be an object'),
        ('missing', lambda proj,t:proj['targets'].pop(t), 'lacks the'),
        ('bool-count', lambda proj,t:proj['targets'][t].__setitem__(
            'expected_projection_count', True
        ), 'count disagrees'),
        ('wrong-count', lambda proj,t:proj['targets'][t].__setitem__(
            'expected_projection_count', 99
        ), 'count disagrees'),
        ('bad-path', lambda proj,t:proj['targets'][t].__setitem__(
            'target_manifest_path', 'wrong'
        ), 'path disagrees'),
    )
    for target_id, builder in TARGETS:
        for name, mutate, expected in cases:
            errors, report, wrote = run_mutation(
                target_id, builder, lambda proj: mutate(proj,target_id),
                target_file='projection',
            )
            assert any(expected in error for error in errors), (target_id, name, errors)
            assert report.get('success') is False and not wrote, (target_id,name,report)



def test_malformed_behavior_module_inventory() -> None:
    cases = (
        ('non-object', lambda m: m['modules'].append(None), 'non-object entry'),
        ('duplicate', lambda m: m['modules'].append(dict(m['modules'][0])),
         'Duplicate behavior module id'),
        ('unhashable-id', lambda m: m['modules'][0].__setitem__('id', []),
         'invalid module id'),
        ('empty-id', lambda m: m['modules'][0].__setitem__('id', ''),
         'invalid module id'),
    )
    for target_id, builder in TARGETS:
        assert behavior_snapshot.index_governed_behavior_modules is kernel.index_governed_behavior_modules
        for name, mutation, message in cases:
            errors, report, wrote = run_mutation(
                target_id, builder, mutation, target_file='behavior',
            )
            assert any(message in error for error in errors), (target_id,name,errors)
            assert not report['success'] and not wrote, (target_id,name,report)


def test_malformed_source_item_and_capabilities() -> None:
    for target_id, builder in TARGETS:
        for name, mutation, message in (
            ('unhashable-item-id', lambda src:next(item for item in src['behavior_items']
               if target_id in item.get('applies_to',[])).__setitem__('id', []),
               'behavior item id'),
            ('nonstring-item-id', lambda src:next(item for item in src['behavior_items']
               if target_id in item.get('applies_to',[])).__setitem__('id', 12),
               'behavior item id'),
            ('target-capabilities-none',lambda src:next(item for item in src['targets']
               if item.get('id')==target_id).__setitem__('capabilities',None),
               'capabilities must contain exactly'),
            ('target-capabilities-array',lambda src:next(item for item in src['targets']
               if item.get('id')==target_id).__setitem__('capabilities',[]),
               'capabilities must contain exactly'),
            ('dispositions-is-list',lambda src:next(item for item in src['behavior_items']
               if target_id in item.get('applies_to',[])).__setitem__(
                   'target_dispositions', []),
               'lacks a valid'),
        ):
            errors, report, wrote = run_mutation(target_id,builder,mutation)
            assert any(message in error for error in errors),(target_id,name,errors)
            assert not report['success'] and not wrote,(target_id,name,report)



def test_safe_targets_and_shared_owners() -> None:
    for target_id, builder in TARGETS:
        assert behavior_snapshot.validate_behavior_disposition is kernel.validate_behavior_disposition
        assert source_contract.select_governed_source_target is kernel.select_governed_source_target
        assert builder.validate_projection_manifest_binding is kernel.validate_projection_manifest_binding
        tmp, repo, adapter = stage(target_id)
        try:
            # Materialize first; then verify check mode accepts the exact bytes.
            for check in (False, True):
                errors, report = builder.build_package(repo, adapter, check=check)
                assert not errors and report['success'], (target_id, check, errors)
            print('PASS safe materialize/check',target_id)
        finally:
            tmp.cleanup()


def main():
    test_source_dispositions_and_modes()
    test_target_uniqueness_and_shape()
    test_projection_binding_shape_and_count()
    test_malformed_behavior_module_inventory()
    test_malformed_source_item_and_capabilities()
    test_safe_targets_and_shared_owners()
    print('PASS: strict DCOIR/USB disposition, source-target and Knowledge manifest gates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
