$ErrorActionPreference = 'Stop'

$branch = 'issue-421-openai-gpt-deployment-builder'
$expectedHead = 'a30fc3f8a532e2733ed45a72c3d374c3ce9dd6fc'
$worktree = Join-Path $env:RUNNER_TEMP 'issue421-openai-bundle-worktree-v2'

function Invoke-Checked([string]$Label, [scriptblock]$Action) {
  Write-Host "=== $Label ==="
  & $Action
  if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit $LASTEXITCODE" }
}

if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }

git fetch --no-tags origin $branch main
if ($LASTEXITCODE -ne 0) { throw 'Unable to fetch issue #421 branch/main' }
$remoteHead = (git rev-parse "origin/$branch").Trim()
if ($remoteHead -ne $expectedHead) { throw "Issue #421 branch moved: expected $expectedHead, found $remoteHead" }

git worktree add --detach $worktree "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Unable to create isolated issue #421 worktree' }

try {
  Push-Location $worktree
  try {
    @'
import json
from pathlib import Path

builder_path = Path('project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py')
builder = builder_path.read_text(encoding='utf-8')

old_copy = '''def _copy_record(source: Path, destination: Path, delivery_root: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    destination.write_bytes(data)
    return {
        "delivery_path": destination.relative_to(delivery_root).as_posix(),
        "source_path": source.as_posix(),
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
    }
'''
new_copy = '''def _copy_record(
    source: Path,
    destination: Path,
    delivery_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    destination.write_bytes(data)
    return {
        "delivery_path": destination.relative_to(delivery_root).as_posix(),
        "source_path": source.relative_to(repo_root).as_posix(),
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
    }
'''
if builder.count(old_copy) != 1:
    raise SystemExit(f'expected one _copy_record definition, found {builder.count(old_copy)}')
builder = builder.replace(old_copy, new_copy, 1)
for old_call, new_call in (
    ('_copy_record(source, destination_root / name, delivery_root)', '_copy_record(source, destination_root / name, delivery_root, repo_root)'),
    ('_copy_record(source, destination_root / "Knowledge" / source.name, delivery_root)', '_copy_record(source, destination_root / "Knowledge" / source.name, delivery_root, repo_root)'),
    ('_copy_record(guide_path, delivery_root / GUIDE.name, delivery_root)', '_copy_record(guide_path, delivery_root / GUIDE.name, delivery_root, repo_root)'),
    ('_copy_record(parity_json_path, delivery_root / PARITY_JSON, delivery_root)', '_copy_record(parity_json_path, delivery_root / PARITY_JSON, delivery_root, repo_root)'),
    ('_copy_record(parity_md_path, delivery_root / PARITY_MD, delivery_root)', '_copy_record(parity_md_path, delivery_root / PARITY_MD, delivery_root, repo_root)'),
):
    if old_call not in builder:
        raise SystemExit(f'expected builder call not found: {old_call}')
    builder = builder.replace(old_call, new_call)

old_boundary = '''    if not output_dir.is_relative_to(repo_root) or output_dir == repo_root:
        errors.append("output_dir must be a non-root path inside the repository")
    if not parity_root.is_relative_to(repo_root):
        errors.append("parity_root must be inside the repository")
    output_dir.mkdir(parents=True, exist_ok=True)

    commit = _source_commit(repo_root, source_commit)
'''
new_boundary = '''    if not output_dir.is_relative_to(repo_root) or output_dir == repo_root:
        errors.append("output_dir must be a non-root path inside the repository")
    if not parity_root.is_relative_to(repo_root):
        errors.append("parity_root must be inside the repository")
    commit = _source_commit(repo_root, source_commit)
    if errors:
        return errors, {
            "schema": REPORT_SCHEMA,
            "success": False,
            "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": commit,
            "delivery_root": None,
            "zip_path": None,
            "zip_sha256": None,
            "target_count": 0,
            "targets": [],
            "static_parity_status": None,
            "live_parity_status": None,
            "errors": errors,
        }
    output_dir.mkdir(parents=True, exist_ok=True)

'''
if builder.count(old_boundary) != 1:
    raise SystemExit(f'expected one output-boundary block, found {builder.count(old_boundary)}')
builder = builder.replace(old_boundary, new_boundary, 1)
if '"source_path": source.as_posix()' in builder:
    raise SystemExit('absolute source_path implementation remains')
builder_path.write_text(builder, encoding='utf-8')

# Strengthen deterministic and path-safety tests.
test_path = Path('project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py')
test = test_path.read_text(encoding='utf-8')
insert_before = 'def test_knowledge_drift_fails_closed() -> None:\n'
new_test = '''def test_cross_checkout_root_determinism() -> None:
    td_a, repo_a = stage_repo()
    td_b, repo_b = stage_repo()
    try:
        errors_a, report_a = _build(repo_a, "out")
        errors_b, report_b = _build(repo_b, "out")
        assert not errors_a, errors_a
        assert not errors_b, errors_b
        zip_a = repo_a / report_a["zip_path"]
        zip_b = repo_b / report_b["zip_path"]
        assert zip_a.read_bytes() == zip_b.read_bytes()
        manifest_a = json.loads(
            (repo_a / "project_sources/validation/out" / module.DELIVERY_ROOT_NAME / "delivery_manifest.json").read_text(encoding="utf-8")
        )
        for target in manifest_a["targets"]:
            for record in target["package_files"] + target["knowledge_files"]:
                assert not Path(record["source_path"]).is_absolute(), record
                assert not record["source_path"].startswith(repo_a.as_posix()), record
    finally:
        td_b.cleanup()
        td_a.cleanup()


'''
if new_test not in test:
    if test.count(insert_before) != 1:
        raise SystemExit(f'expected one selftest insertion point, found {test.count(insert_before)}')
    test = test.replace(insert_before, new_test + insert_before, 1)
list_marker = '        test_combined_delivery_and_determinism,\n'
if '        test_cross_checkout_root_determinism,\n' not in test:
    if test.count(list_marker) != 1:
        raise SystemExit(f'expected one tests-list marker, found {test.count(list_marker)}')
    test = test.replace(list_marker, list_marker + '        test_cross_checkout_root_determinism,\n', 1)
old_escape = '''        assert errors
        assert report["success"] is False
        assert any("output_dir must be" in error for error in errors), errors
'''
new_escape = '''        assert errors
        assert report["success"] is False
        assert report["delivery_root"] is None
        assert report["zip_path"] is None
        assert any("output_dir must be" in error for error in errors), errors
        assert not (Path(outside.name) / module.DELIVERY_ROOT_NAME).exists()
'''
if test.count(old_escape) != 1:
    raise SystemExit(f'expected one output-escape assertion block, found {test.count(old_escape)}')
test = test.replace(old_escape, new_escape, 1)
test_path.write_text(test, encoding='utf-8')

profiles_path = Path('.github/github_actions/workflow_required_surface_profiles.json')
profiles = json.loads(profiles_path.read_text(encoding='utf-8'))
profiles['manual_openai_gpt_deployment_package_build'] = [
    'project_sources/agent_runtime/README.md',
    'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
    'project_sources/agent_runtime/Behavior_Module_Manifest.json',
    'project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
    'project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py',
    'project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py',
    'project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py',
    'project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py',
    'project_sources/agent_runtime/tools/project_agent_knowledge.py',
    'project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py',
    'project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py',
    'project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py',
    'project_sources/agent_runtime/tools/build_openai_usb_reporting.py',
    'project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py',
    'project_sources/agent_runtime/tools/report_agent_release_parity.py',
    'project_sources/agent_runtime/tests/report_agent_release_parity_selftest.py',
    'project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py',
    'project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py',
    'project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md',
    'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/GPT_Configuration.json',
    'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/Instructions.md',
    'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/manifest.json',
    'project_sources/agent_runtime/generated/packages/openai_usb_reporting/GPT_Configuration.json',
    'project_sources/agent_runtime/generated/packages/openai_usb_reporting/Instructions.md',
    'project_sources/agent_runtime/generated/packages/openai_usb_reporting/manifest.json',
    'project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst/manifest.json',
    'project_sources/agent_runtime/generated/knowledge/openai_usb_reporting/manifest.json',
    '.github/github_actions/tools/surface_delivery_zip.py',
    '.github/workflows/manual-openai-gpt-deployment-package-build.yml',
    '.github/workflows/reusable-openai-gpt-deployment-package-build.yml',
]
profiles_path.write_text(json.dumps(profiles, indent=2) + '\n', encoding='utf-8')

contracts_path = Path('.github/github_actions/workflow_modularization_contracts.json')
contracts = json.loads(contracts_path.read_text(encoding='utf-8'))
contracts['existing_workflow_count'] = 30
contracts['primary_workflow_count'] = 30
contracts['reusable_workflow_count'] = 29
families = contracts['required_contract_families']
if 'openai-gpt-bundle' not in families:
    insert_at = families.index('gemini-bundle') + 1 if 'gemini-bundle' in families else len(families)
    families.insert(insert_at, 'openai-gpt-bundle')
new_contract = {
    'acceptance_evidence': 'Exact-head ten-command agent-runtime validation, combined release self-test, static parity report, direct two-GPT delivery artifact contents/hashes, full evidence artifact, workflow run/job readback, and manual/live evidence boundary.',
    'contract_family': 'openai-gpt-bundle',
    'family': 'OpenAI GPT packaging',
    'file': '.github/workflows/manual-openai-gpt-deployment-package-build.yml',
    'migration_status': 'active',
    'risk': 'medium',
    'rollback': 'Remove the OpenAI deployment package entry/reusable workflows and retain the existing target-specific builders and manual WebUI procedure.',
    'target_architecture': 'One operator-triggered entry workflow calls a family-specific reusable workflow that runs the governed agent-runtime validation contract, unified static parity reporting, deterministic two-target delivery assembly, direct artifact surfacing, evidence upload, and ChatGPT workflow report section without mutating live OpenAI targets.',
}
workflow_contracts = contracts['workflow_contracts']
workflow_contracts[:] = [entry for entry in workflow_contracts if entry.get('file') != new_contract['file']]
insert_at = next((i + 1 for i, entry in enumerate(workflow_contracts) if entry.get('file') == '.github/workflows/manual-gemini-bundle-build.yml'), len(workflow_contracts))
workflow_contracts.insert(insert_at, new_contract)
contracts_path.write_text(json.dumps(contracts, indent=2) + '\n', encoding='utf-8')

readme_path = Path('project_sources/agent_runtime/README.md')
readme = readme_path.read_text(encoding='utf-8')
marker = '## IOC Enrichment\n'
section = '''## Manual OpenAI GPT Deployment Package Build

The operator-facing workflow `.github/workflows/manual-openai-gpt-deployment-package-build.yml` (`07 Operator - Build OpenAI GPT Deployment Packages`) builds both OpenAI WebUI deployment targets in one manual run. It mirrors the established Gemini delivery pattern: a thin `workflow_dispatch` entry calls a reusable workflow module, runs the governed ten-command agent-runtime validation contract, builds the unified static release/parity report, assembles one deterministic delivery ZIP, surfaces a direct operator artifact, retains a fuller evidence artifact, and emits a ChatGPT workflow report section.

The direct artifact expands the production ZIP so the operator can open one download and find `AFRICOM_DCOIR_Analyst/` and `AFRICOM_USB_Reporting/` beneath `OpenAI_GPT_Deployment_Packages/`. Each target folder contains `GPT_Configuration.json`, `Instructions.md`, `manifest.json`, and a `Knowledge/` folder containing exactly the governed seven or two files. The package root also carries the deployment/readback guide, release/parity JSON and Markdown, and delivery manifests.

The workflow fails closed on source/package drift, Knowledge hash/count drift, blocking static parity gaps, source-commit mismatch, unsafe output paths, or release-builder self-test failure. Its successful output is still static deployment material only: it does not create or modify either hosted GPT and does not prove live GPT-5.4 behavior. Manual WebUI deployment and live readback remain governed by `docs/Release_Parity_Deployment_Readback.md`.

Run it from GitHub Actions when an operator-ready package is needed. For local or runner-side release proof, the underlying deterministic builder is:

```bash
python project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py --source-commit <tested-sha> --output-dir project_sources/validation/out_openai_gpt_deployment --parity-root project_sources/validation/out_openai_gpt_deployment/parity
```

'''
if section not in readme:
    if marker not in readme: raise SystemExit('README insertion marker not found')
    readme = readme.replace(marker, section + marker, 1)
readme_path.write_text(readme, encoding='utf-8')

guide_path = Path('project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md')
guide = guide_path.read_text(encoding='utf-8')
guide_marker = '## AFRICOM DCOIR Analyst manual deployment\n'
guide_section = '''## One-click OpenAI deployment package build

For the normal operator release lane, prefer GitHub Actions workflow `07 Operator - Build OpenAI GPT Deployment Packages`. One manual run validates both OpenAI targets, produces the unified static parity report, and creates one direct delivery artifact containing both GPT folders plus their ordered Knowledge files and deployment/readback evidence. Download that direct artifact and use its contents for the manual WebUI steps below.

The workflow is a packaging convenience, not a deployment agent. A successful run does not modify either live GPT and does not change the live-readback requirements in this procedure.

'''
if guide_section not in guide:
    if guide_marker not in guide: raise SystemExit('Deployment guide insertion marker not found')
    guide = guide.replace(guide_marker, guide_section + guide_marker, 1)
guide_path.write_text(guide, encoding='utf-8')
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Issue #421 governed source alignment edit failed' }

    Invoke-Checked 'Regenerate workflow inventory' { python .github/github_actions/tools/build_workflow_inventory.py }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed before commit' }

    git add project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py .github/github_actions/workflow_required_surface_profiles.json .github/github_actions/workflow_modularization_contracts.json .github/github_actions/workflow_inventory.json .github/github_actions/workflow_inventory.md project_sources/agent_runtime/README.md project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { throw 'Issue #421 governed source alignment produced no staged changes' }
    git -c user.name='Malware Devil' -c user.email='34285973+malwaredevil@users.noreply.github.com' commit -m 'Harden OpenAI deployment bundle release'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to commit issue #421 source alignment' }
    $testedSha = (git rev-parse HEAD).Trim()
    Write-Host "tested_branch_head=$testedSha"

    Invoke-Checked 'Compile combined OpenAI deployment release builder' { python -m py_compile project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py }
    Invoke-Checked 'Combined OpenAI deployment release self-tests' { python project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py }
    Invoke-Checked 'OpenAI deployment required surfaces' { python .github/github_actions/tools/check_required_surfaces.py --profile manual_openai_gpt_deployment_package_build }
    Invoke-Checked 'Workflow inventory check' { python .github/github_actions/tools/build_workflow_inventory.py --check }
    Invoke-Checked 'Workflow modularization contracts' { python .github/github_actions/tools/check_workflow_modularization_contracts.py }
    Invoke-Checked 'Reusable workflow contracts' { python .github/github_actions/tools/audit_reusable_contracts.py }
    Invoke-Checked 'Workflow consistency drift' { python .github/github_actions/tools/check_workflow_consistency_drift.py }
    Invoke-Checked 'Workflow action versions' { python .github/github_actions/tools/check_workflow_action_versions.py }

    Invoke-Checked '1 Shared source contract' { python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py }
    Invoke-Checked '2 Shared source contract self-tests' { python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py }
    Invoke-Checked '3 Behavior adapter materialization check' { python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check }
    Invoke-Checked '4 Behavior adapter self-tests' { python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py }
    Invoke-Checked '5 Knowledge projection check' { python project_sources/agent_runtime/tools/project_agent_knowledge.py --check }
    Invoke-Checked '6 Knowledge projection self-tests' { python project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py }
    Invoke-Checked '7 OpenAI DCOIR package check' { python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check }
    Invoke-Checked '8 OpenAI DCOIR package self-tests' { python project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py }
    Invoke-Checked '9 OpenAI USB package check' { python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check }
    Invoke-Checked '10 OpenAI USB package self-tests plus unified parity' { python project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py }

    Invoke-Checked 'Exact-head unified parity report' { python project_sources/agent_runtime/tools/report_agent_release_parity.py --source-commit $testedSha --output-root project_sources/validation/out_issue421_openai_delivery/parity }
    Invoke-Checked 'Exact-head combined OpenAI deployment build' { python project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py --source-commit $testedSha --output-dir project_sources/validation/out_issue421_openai_delivery --parity-root project_sources/validation/out_issue421_openai_delivery/parity }
    Invoke-Checked 'Surface direct delivery artifact locally' { python .github/github_actions/tools/surface_delivery_zip.py --build-report project_sources/validation/out_issue421_openai_delivery/build_openai_gpt_deployment_release_report.json --output-dir project_sources/validation/out_issue421_openai_delivery/direct_artifact --manifest-dir project_sources/validation/out_issue421_openai_delivery/surface_manifest --extract-for-artifact --artifact-label dcoir-openai-gpt-deployment-packages --workflow-name manual-openai-gpt-deployment-package-build }

    @'
import json
import zipfile
from pathlib import Path
root = Path('project_sources/validation/out_issue421_openai_delivery')
report = json.loads((root / 'build_openai_gpt_deployment_release_report.json').read_text(encoding='utf-8'))
if not report.get('success') or report.get('static_parity_status') != 'pass': raise SystemExit(f'combined release report not clean: {report}')
zip_path = Path(report['zip_path'])
with zipfile.ZipFile(zip_path) as zf: names = zf.namelist()
prefix = 'OpenAI_GPT_Deployment_Packages/'
if sum(name.startswith(prefix + 'AFRICOM_DCOIR_Analyst/Knowledge/') for name in names) != 7: raise SystemExit('DCOIR delivery Knowledge count is not seven')
if sum(name.startswith(prefix + 'AFRICOM_USB_Reporting/Knowledge/') for name in names) != 2: raise SystemExit('USB delivery Knowledge count is not two')
for required in (prefix + 'AFRICOM_DCOIR_Analyst/GPT_Configuration.json', prefix + 'AFRICOM_DCOIR_Analyst/Instructions.md', prefix + 'AFRICOM_USB_Reporting/GPT_Configuration.json', prefix + 'AFRICOM_USB_Reporting/Instructions.md', prefix + 'delivery_manifest.json', prefix + 'agent_release_parity_report.json', prefix + 'Release_Parity_Deployment_Readback.md'):
    if required not in names: raise SystemExit(f'missing delivery entry: {required}')
print(json.dumps({'success': True, 'zip_path': report['zip_path'], 'zip_sha256': report['zip_sha256'], 'entry_count': len(names)}, indent=2))
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Combined OpenAI delivery ZIP inspection failed' }

    $tracked = git status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect tracked repository state' }
    if ($tracked) { $tracked | Out-Host; throw 'Validation changed tracked repository files' }

    git push origin HEAD:$branch
    if ($LASTEXITCODE -ne 0) { throw 'Push of validated issue #421 head failed' }
    Write-Host "validated_and_pushed_head=$testedSha"
  }
  finally { Pop-Location }
}
finally {
  git worktree remove --force $worktree 2>$null
  git worktree prune
}
