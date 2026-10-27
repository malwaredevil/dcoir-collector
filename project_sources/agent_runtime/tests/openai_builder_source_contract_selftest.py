#!/usr/bin/env python3
"""Independent safe/adversarial source-provenance checks for both GPT builders."""
from __future__ import annotations

import copy
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
from openai_builder_source_contract import (
    load_adapter_source_inputs, read_source_bytes, sha256_bytes,
    validate_source_target_capabilities,
)

TARGETS = (
    ('openai_dcoir_analyst', dcoir, 'OpenAI DCOIR', 'dcoir'),
    ('openai_usb_reporting', usb, 'OpenAI USB Reporting', 'usb'),
)
BASE = Path('project_sources/agent_runtime')


def adapter_path(root: Path, target: str) -> Path:
    return root / BASE / 'provider_adapters' / target / 'Adapter_Manifest.json'


def load(root: Path, path: Path, builder):
    errors = []
    inputs = load_adapter_source_inputs(
        root, path, errors,
        adapter_schema=builder.SCHEMA, target_id=builder.TARGET_ID,
        expected_paths=builder.EXPECTED_PATHS,
        source_schema=builder.SOURCE_SCHEMA,
        behavior_schema=builder.BEHAVIOR_SCHEMA,
        invalid_generated_root=f'.invalid-{builder.TARGET_ID}',
    )
    return inputs, errors


def profile(inputs, target: str, builder, label: str, policy: str):
    errors = []
    actual, capabilities = validate_source_target_capabilities(
        inputs.source_contract, inputs.manifest, errors,
        target_id=target, label=label,
        runtime_model=builder.EXPECTED_RUNTIME_MODEL,
        profile_error_policy=policy,
    )
    return actual, capabilities, errors


def test_actual_safe_source_and_capability_records():
    for target, builder, label, policy in TARGETS:
        inputs, errors = load(ROOT, adapter_path(ROOT, target), builder)
        assert inputs is not None and not errors, (target, errors)
        assert inputs.source_contract_sha == hashlib.sha256(
            (ROOT / builder.EXPECTED_PATHS['source_contract']).read_bytes()
        ).hexdigest()
        assert inputs.generated_root == (ROOT / builder.EXPECTED_PATHS['generated_root']).resolve()
        actual, capabilities, errors = profile(inputs, target, builder, label, policy)
        assert not errors and actual['id'] == target, (target, errors)
        assert capabilities and all(value is False for value in capabilities.values())
        assert sha256_bytes(b'abc') == hashlib.sha256(b'abc').hexdigest()


def test_mutated_adapter_identity_and_commit_fail_closed():
    for target, builder, _, _ in TARGETS:
        baseline = json.loads(adapter_path(ROOT, target).read_text())
        cases = (
            ('schema', 'unknown-adapter', 'Unexpected adapter schema'),
            ('target_id', 'different-target', 'Unexpected adapter target'),
            ('source_base_commit', False, '40-character Git SHA'),
            ('source_base_commit', '0'*39, '40-character Git SHA'),
            ('source_base_commit', 'G'*40, '40-character Git SHA'),
            ('source_base_commit', None, '40-character Git SHA'),
            ('generated_root', 'different-generated-dir', 'generated_root'),
            ('source_contract', 'wrong-contract.json', 'source_contract'),
            ('behavior_module_manifest', 'wrong-behavior.json', 'behavior_module_manifest'),
        )
        with tempfile.TemporaryDirectory(prefix='issue605-source-input-') as temp:
            manifest_path = Path(temp) / 'adapter.json'
            for key, value, expected in cases:
                altered = copy.deepcopy(baseline)
                altered[key] = value
                manifest_path.write_text(json.dumps(altered))
                inputs, errors = load(ROOT, manifest_path, builder)
                assert any(expected in e for e in errors), (target, key, errors)
            manifest_path.write_text('{bad-json')
            inputs, errors = load(ROOT, manifest_path, builder)
            assert inputs is None and any('Invalid JSON in' in e for e in errors)
            manifest_path.write_text('[]')
            inputs, errors = load(ROOT, manifest_path, builder)
            assert inputs is None and any('Expected a JSON object' in e for e in errors)
            manifest_path.unlink()
            inputs, errors = load(ROOT, manifest_path, builder)
            assert inputs is None and any('Missing JSON file' in e for e in errors)


def test_source_target_profile_and_capability_mutants_fail_closed():
    for target, builder, label, policy in TARGETS:
        inputs, errors = load(ROOT, adapter_path(ROOT, target), builder)
        assert inputs is not None and not errors
        cases = (
            ('adapter-caps-object', 'adapter', lambda m: m.__setitem__('capabilities', False), 'must be an object'),
            ('adapter-caps-extra', 'adapter', lambda m: m['capabilities'].__setitem__('unapproved', False), 'exactly the governed keys'),
            ('adapter-caps-true', 'adapter', lambda m: m['capabilities'].__setitem__('web_search', True), 'Unsupported capability must remain false'),
            ('source-caps-object', 'source', lambda m: m.__setitem__('capabilities', []), 'Source contract capabilities must contain exactly'),
            ('source-caps-extra', 'source', lambda m: m['capabilities'].__setitem__('unapproved', False), 'Source contract capabilities must contain exactly'),
            ('source-caps-true', 'source', lambda m: m['capabilities'].__setitem__('web_search', True), 'Source contract target capability drift'),
            ('provider-drift', 'source', lambda m: m.__setitem__('provider', 'invalid'), 'provider drift'),
            ('model-drift', 'source', lambda m: m.__setitem__('runtime_model', 'wrong'), 'runtime'),
            ('mode-drift', 'source', lambda m: m.__setitem__('instruction_mode', 'live'), 'instruction'),
        )
        for name, surface, mutate, expected in cases:
            manifest = copy.deepcopy(inputs.manifest)
            source = copy.deepcopy(inputs.source_contract)
            selected = next(item for item in source['targets'] if item['id'] == target)
            mutate(manifest if surface == 'adapter' else selected)
            _, _, failures = profile(inputs._replace(manifest=manifest, source_contract=source), target, builder, label, policy)
            assert any(expected in e for e in failures), (target, name, failures)


def test_staged_governed_source_schema_and_json_fail_closed():
    for target, builder, _, _ in TARGETS:
        for mutation, expected in (
            ('source-schema', 'Unexpected shared source contract schema'),
            ('behavior-schema', 'Unexpected behavior module manifest schema'),
            ('source-nonobject', 'Expected a JSON object'),
            ('source-missing', 'Missing JSON file'),
            ('behavior-invalid-json', 'Invalid JSON in'),
        ):
            with tempfile.TemporaryDirectory(prefix='issue605-source-stage-') as temp:
                root = Path(temp)
                for key in ('source_contract', 'behavior_module_manifest',
                            'knowledge_projection_manifest', 'knowledge_target_manifest',
                            'canonical_instructions_source', 'behavioral_cases'):
                    relative = Path(builder.EXPECTED_PATHS[key])
                    dst = root / relative
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, dst)
                dst = adapter_path(root, target)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(adapter_path(ROOT, target), dst)
                source = root / builder.EXPECTED_PATHS['source_contract']
                behavior = root / builder.EXPECTED_PATHS['behavior_module_manifest']
                if mutation == 'source-schema':
                    doc = json.loads(source.read_text())
                    doc['schema'] = 'invalid-schema'
                    source.write_text(json.dumps(doc))
                elif mutation == 'behavior-schema':
                    doc = json.loads(behavior.read_text())
                    doc['schema'] = 'invalid-schema'
                    behavior.write_text(json.dumps(doc))
                elif mutation == 'source-nonobject':
                    source.write_text('[]')
                elif mutation == 'source-missing':
                    source.unlink()
                else:
                    behavior.write_text('{invalid json')
                _, errors = load(root, dst, builder)
                assert any(expected in e for e in errors), (target, mutation, errors)


def test_source_path_escape_and_byte_read_errors():
    for target, builder, _, _ in TARGETS:
        base = json.loads(adapter_path(ROOT, target).read_text())
        with tempfile.TemporaryDirectory(prefix='issue605-source-escape-') as temp:
            doc = Path(temp) / 'adapter.json'
            for field, bad in (
                ('generated_root', chr(46)*2 + '/escape'),
                ('source_contract', chr(46)*2 + '/escape'),
                ('behavior_module_manifest', '/absolute-escape'),
            ):
                corrupted = copy.deepcopy(base)
                corrupted[field] = bad
                doc.write_text(json.dumps(corrupted))
                _, errors = load(ROOT, doc, builder)
                assert errors and any('traversal' in e or 'absolute' in e for e in errors), (target, field, errors)
            valid = Path(temp) / 'source.json'
            valid.write_bytes(b'known-bytes')
            errors = []
            assert read_source_bytes(valid, 'source', errors) == b'known-bytes' and not errors
            assert read_source_bytes(Path(temp) / 'missing', 'source', errors) == b''
            assert any('Missing source:' in e for e in errors)
            errors = []
            assert read_source_bytes(Path(temp), 'directory', errors) == b''
            assert any('Unreadable directory:' in e for e in errors)


def main() -> int:
    tests = (
        test_actual_safe_source_and_capability_records,
        test_mutated_adapter_identity_and_commit_fail_closed,
        test_source_target_profile_and_capability_mutants_fail_closed,
        test_staged_governed_source_schema_and_json_fail_closed,
        test_source_path_escape_and_byte_read_errors,
    )
    for case in tests:
        case()
    print(json.dumps({'success': True, 'tests': [case.__name__ for case in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
