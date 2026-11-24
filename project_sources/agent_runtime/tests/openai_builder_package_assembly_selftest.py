#!/usr/bin/env python3
"""Two-target package assembly safe, hostile, boundary and byte parity checks."""
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
import openai_builder_package_assembly as assembly
import openai_builder_pipeline as pipeline
import openai_builder_source_contract as source_contract
import openai_builder_validation_kernel as validation_kernel
import openai_webui_contract as webui

TARGETS = (('openai_dcoir_analyst', dcoir), ('openai_usb_reporting', usb))
BASE = Path('project_sources/agent_runtime')


def stage(target_id: str):
    temporary = tempfile.TemporaryDirectory(prefix='issue605-package-assembly-')
    repo = Path(temporary.name)
    for rel in (
        BASE / 'Shared_Agent_Source_Manifest.json',
        BASE / 'Behavior_Module_Manifest.json',
        BASE / 'Knowledge_Projection_Manifest.json',
    ):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    for rel in (BASE / 'behavior_modules',
                BASE / f'provider_adapters/{target_id}',
                BASE / f'generated/knowledge/{target_id}'):
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / rel, dst)
    adapter = repo / BASE / f'provider_adapters/{target_id}/Adapter_Manifest.json'
    pkg = repo / BASE / f'generated/packages/{target_id}'
    return temporary, repo, adapter, pkg


def mutate_adapter(path: Path, mutate):
    data = json.loads(path.read_text(encoding='utf-8'))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def test_valid_package_manifest_configuration_and_hash_scope():
    for target, builder in TARGETS:
        assert builder.assemble_package_files is assembly.assemble_package_files
        assert builder.PACKAGE_SETTINGS.target_id == target
        assert builder.PACKAGE_SETTINGS.expected_outputs == builder.EXPECTED_OUTPUTS
        tmp, repo, adapter, pkg = stage(target)
        try:
            errors, report = builder.build_package(repo, adapter, check=False)
            assert not errors and report['success'], (target, errors)
            assert report['generated_file_count'] == 3
            check_errors, check_report = builder.build_package(repo, adapter, check=True)
            assert not check_errors and check_report['success']
            assert sorted(p.name for p in pkg.iterdir()) == ['GPT_Configuration.json', 'Instructions.md', 'manifest.json']
            for name in ('Instructions.md', 'GPT_Configuration.json', 'manifest.json'):
                rel = BASE / f'generated/packages/{target}/{name}'
                assert (repo / rel).read_bytes() == (ROOT / rel).read_bytes(), (target, name)
            data = json.loads((pkg / 'manifest.json').read_text())
            config = json.loads((pkg / 'GPT_Configuration.json').read_text())
            assert data['schema'] == builder.PACKAGE_SETTINGS.package_schema
            assert data['target_id'] == config['target_id'] == target
            assert data['manual_deployment_required'] is True
            assert data['live_webui_validation_performed'] is False
            keys = list(data['source_contracts'])
            expected_keys = (list(builder.EXPECTED_PATHS)[:6] if target == 'openai_dcoir_analyst'
                             else ['canonical_instructions_source', 'behavioral_cases'])
            assert keys == sorted(expected_keys), (target, keys)
            for item in data['generated_files']:
                p = repo / item['path']
                assert item['sha256'] == hashlib.sha256(p.read_bytes()).hexdigest()
                assert item['bytes'] == p.stat().st_size
        finally:
            tmp.cleanup()


def test_editor_and_starter_mutations_fail_closed_without_writing():
    variants = (
        ('editor-not-object', lambda x: x.__setitem__('editor', None), 'editor configuration must be an object'),
        ('name-mismatch', lambda x: x['editor'].__setitem__('name', 'other'), 'Editor name must remain'),
        ('missing-description', lambda x: x['editor'].pop('description'), 'description must be a non-empty string'),
        ('blank-description', lambda x: x['editor'].__setitem__('description', ' '), 'description must be a non-empty string'),
        ('lone-surrogate-description', lambda x: x['editor'].__setitem__('description', chr(0xd800)), 'lone UTF-16 surrogate'),
        ('description-over-ceiling', lambda x: x['editor'].__setitem__('description', 'A'*301), 'Description exceeds character ceiling'),
        ('ceiling-bool', lambda x: x.__setitem__('description_character_ceiling', True), 'description_character_ceiling must remain'),
        ('ceiling-float', lambda x: x.__setitem__('description_character_ceiling', 300.0), 'description_character_ceiling must remain'),
        ('no-starters', lambda x: x['editor'].__setitem__('conversation_starters', None), 'Exactly four non-empty'),
        ('three-starters', lambda x: x['editor']['conversation_starters'].pop(), 'Exactly four non-empty'),
        ('blank-starter', lambda x: x['editor']['conversation_starters'].__setitem__(0, ' '), 'Exactly four non-empty'),
        ('duplicate-starter', lambda x: x['editor']['conversation_starters'].__setitem__(1, x['editor']['conversation_starters'][0]), 'Conversation starters must be unique'),
        ('surrogate-starter', lambda x: x['editor']['conversation_starters'].__setitem__(0, chr(0xd800)), 'Conversation starters must not contain lone UTF-16'),
    )
    for target, builder in TARGETS:
        for name, mutation, expected in variants:
            tmp, repo, adapter, pkg = stage(target)
            try:
                mutate_adapter(adapter, mutation)
                errors, report = builder.build_package(repo, adapter, check=False)
                assert not report['success'] and any(expected in e for e in errors), (target, name, errors)
                assert not pkg.exists(), (target, name, 'unexpected package materialization')
            finally:
                tmp.cleanup()


def test_output_map_and_escape_mutations_fail_closed():
    variants = (
        ('map-missing', lambda x: x.pop('generated_outputs'), 'generated_outputs must be an object'),
        ('map-list', lambda x: x.__setitem__('generated_outputs', []), 'generated_outputs must be an object'),
        ('instructions-missing', lambda x: x['generated_outputs'].pop('instructions'), 'generated instructions must remain bound'),
        ('instructions-rebound', lambda x: x['generated_outputs'].__setitem__('instructions', 'elsewhere.md'), 'generated instructions must remain bound'),
        ('configuration-rebound', lambda x: x['generated_outputs'].__setitem__('configuration', 'another.json'), 'generated configuration must remain bound'),
        ('manifest-rebound', lambda x: x['generated_outputs'].__setitem__('package_manifest', 'wrong.json'), 'generated package_manifest must remain bound'),
        ('absolute-outside', lambda x: x['generated_outputs'].__setitem__('instructions', '/forbidden/output.md'), 'absolute'),
        ('traversal-outside', lambda x: x['generated_outputs'].__setitem__('instructions', chr(46)*2+'/escape.md'), 'traversal'),
        ('config-nonstring', lambda x: x['generated_outputs'].__setitem__('configuration', True), 'generated configuration'),
    )
    for target, builder in TARGETS:
        for name, mutation, expected in variants:
            tmp, repo, adapter, pkg = stage(target)
            try:
                mutate_adapter(adapter, mutation)
                errors, report = builder.build_package(repo, adapter, check=False)
                assert not report['success'] and any(expected in e for e in errors), (target,name,errors)
                assert not pkg.exists(), (target,name,'unsafe materialization')
            finally:
                tmp.cleanup()


def test_generated_file_drift_and_extra_files_never_report_success():
    for target, builder in TARGETS:
        for name in ('GPT_Configuration.json', 'Instructions.md', 'manifest.json'):
            tmp, repo, adapter, pkg = stage(target)
            try:
                errors, report = builder.build_package(repo, adapter, check=False)
                assert not errors and report['success']
                file = pkg / name
                file.write_bytes(b'modified-package-content')
                errors, report = builder.build_package(repo, adapter, check=True)
                assert errors and not report['success']
                assert any('Generated package drift:' in e for e in errors), (target,name,errors)
                assert file.read_bytes() == b'modified-package-content'
            finally:
                tmp.cleanup()
        tmp, repo, adapter, pkg = stage(target)
        try:
            errors, report = builder.build_package(repo, adapter, check=False)
            assert not errors and report['success']
            unexpected = pkg / 'unexpected.txt'
            unexpected.write_text('sentinel', encoding='utf-8')
            errors, report = builder.build_package(repo, adapter, check=True)
            assert errors and not report['success']
            assert any('unexpected' in e.lower() or 'extra' in e.lower() for e in errors), (target,errors)
            assert unexpected.read_text(encoding='utf-8') == 'sentinel'
        finally:
            tmp.cleanup()



def test_shared_pipeline_owner_and_target_specifications():
    import ast
    import inspect

    for target, builder in TARGETS:
        spec = builder.TARGET_SPEC
        assert isinstance(spec, pipeline.BuilderSpec)
        assert builder.run_builder_pipeline is pipeline.run_builder_pipeline
        assert spec.target_id == builder.TARGET_ID == target
        assert spec.package_settings is builder.PACKAGE_SETTINGS
        assert spec.expected_paths is builder.EXPECTED_PATHS
        assert spec.projection_before_target is (target == 'openai_dcoir_analyst')
        # There must be one source-of-truth pipeline, not duplicated validators.
        build_function = ast.parse(inspect.getsource(builder.build_package)).body[0]
        assert len(build_function.body) == 1
        assert isinstance(build_function.body[0], ast.Return)
        assert isinstance(build_function.body[0].value, ast.Call)
        assert build_function.body[0].value.func.id == 'run_builder_pipeline'


def test_pipeline_hostile_order_and_cross_target_binding():
    for target, builder in TARGETS:
        tmp, repo, adapter, pkg = stage(target)
        try:
            # Simultaneously corrupt the knowledge hash and behavior coverage.
            # The old targets differ in which error must be observed first.
            mutate_adapter(adapter, lambda a: a.__setitem__('coverage', []))
            knowledge = repo / BASE / f'generated/knowledge/{target}/manifest.json'
            data = json.loads(knowledge.read_text(encoding='utf-8'))
            data['source_contract_sha256'] = '0' * 64
            knowledge.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            errors, report = builder.build_package(repo, adapter, check=False)
            assert not report['success'] and not pkg.exists(), (target, errors)
            assert len(errors) == 3, (target, errors)
            hash_error = errors.index('Knowledge target source-contract hash drift')
            coverage_error = next(i for i, e in enumerate(errors) if e.startswith('Behavior coverage must exactly match'))
            if target == 'openai_dcoir_analyst':
                assert hash_error < coverage_error, (target, errors)
            else:
                assert coverage_error < hash_error, (target, errors)
        finally:
            tmp.cleanup()

        # A valid target must reject another builder's manifest, without output.
        tmp, repo, adapter, pkg = stage(target)
        try:
            other = usb if target == 'openai_dcoir_analyst' else dcoir
            errors, report = pipeline.run_builder_pipeline(
                repo, adapter, check=False, spec=other.TARGET_SPEC,
            )
            assert errors and not report['success'] and not pkg.exists(), (target, errors)
        finally:
            tmp.cleanup()



def test_builder_legacy_exports_resolve_to_shared_owners():
    canonical = {
        'assemble_package_files': assembly.assemble_package_files,
        '_read_bytes': source_contract.read_source_bytes,
        'validate_projection_manifest_binding': validation_kernel.validate_projection_manifest_binding,
        '_contains_lone_surrogate': webui.contains_lone_surrogate,
        '_webui_character_count': webui.webui_character_count,
        '_webui_paste_safe_character_count': webui.webui_paste_safe_character_count,
    }
    for target, builder in TARGETS:
        assert builder.PackageSettings is assembly.PackageSettings
        assert builder.EXPECTED_INSTRUCTION_CHARACTER_CEILING == 8000
        assert builder.EXPECTED_DESCRIPTION_CHARACTER_CEILING == 300
        for alias, owner in canonical.items():
            assert alias not in vars(builder), (target, alias)
            assert alias in dir(builder), (target, alias)
            assert getattr(builder, alias) is owner, (target, alias)
            imported = __import__(builder.__name__, fromlist=[alias])
            assert getattr(imported, alias) is owner, (target, alias)
        for missing in ('not_an_export', '_unsafe_export', 'unknown__'):
            assert not hasattr(builder, missing), (target, missing)
            try:
                getattr(builder, missing)
            except AttributeError:
                pass
            else:
                raise AssertionError((target, missing, 'unexpected export'))
        assert builder._webui_character_count('x\U0001f600') == 3
        assert builder._webui_paste_safe_character_count('a\rb') == 4


def main() -> int:
    tests = (
        test_valid_package_manifest_configuration_and_hash_scope,
        test_editor_and_starter_mutations_fail_closed_without_writing,
        test_output_map_and_escape_mutations_fail_closed,
        test_generated_file_drift_and_extra_files_never_report_success,
        test_shared_pipeline_owner_and_target_specifications,
        test_pipeline_hostile_order_and_cross_target_binding,
        test_builder_legacy_exports_resolve_to_shared_owners,
    )
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [t.__name__ for t in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
