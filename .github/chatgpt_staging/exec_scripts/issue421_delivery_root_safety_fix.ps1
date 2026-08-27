$ErrorActionPreference = 'Stop'

$branch = 'issue-421-openai-gpt-deployment-builder'
$expectedHead = 'f8fd3a4637b75e5268b0380bfeac00fdda62b8fe'
$worktree = Join-Path $env:RUNNER_TEMP 'issue421-delivery-root-safety-fix'

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
from pathlib import Path

builder_path = Path('project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py')
builder = builder_path.read_text(encoding='utf-8')
old = '''    delivery_root = output_dir / DELIVERY_ROOT_NAME
    if delivery_root.exists():
        if delivery_root.is_symlink() or not delivery_root.is_dir():
            errors.append(f"Unsafe existing delivery root: {delivery_root.as_posix()}")
        else:
            shutil.rmtree(delivery_root)
    delivery_root.mkdir(parents=True, exist_ok=True)
'''
new = '''    delivery_root = output_dir / DELIVERY_ROOT_NAME
    if delivery_root.exists() or delivery_root.is_symlink():
        if delivery_root.is_symlink() or not delivery_root.is_dir():
            errors.append(f"Unsafe existing delivery root: {delivery_root.as_posix()}")
            return errors, {
                "schema": REPORT_SCHEMA,
                "success": False,
                "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": commit,
                "delivery_root": delivery_root.relative_to(repo_root).as_posix(),
                "zip_path": None,
                "zip_sha256": None,
                "target_count": 0,
                "targets": [],
                "static_parity_status": parity.get("static_parity_status"),
                "live_parity_status": parity.get("live_parity_status"),
                "errors": errors,
            }
        shutil.rmtree(delivery_root)
    delivery_root.mkdir(parents=True, exist_ok=True)
'''
if builder.count(old) != 1:
    raise SystemExit(f'expected one delivery-root block, found {builder.count(old)}')
builder = builder.replace(old, new, 1)
builder_path.write_text(builder, encoding='utf-8')

test_path = Path('project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py')
test = test_path.read_text(encoding='utf-8')
insert_before = 'def test_output_escape_is_rejected() -> None:\n'
new_tests = '''def test_unsafe_existing_delivery_root_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        unsafe = output_dir / module.DELIVERY_ROOT_NAME
        unsafe.write_text("do-not-overwrite\\n", encoding="utf-8")
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Unsafe existing delivery root" in error for error in errors), errors
        assert unsafe.is_file()
        assert unsafe.read_text(encoding="utf-8") == "do-not-overwrite\\n"
    finally:
        td.cleanup()


def test_existing_delivery_root_symlink_fails_closed_when_supported() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = repo / "project_sources/validation/symlink-target"
        target.mkdir(parents=True, exist_ok=True)
        marker = target / "marker.txt"
        marker.write_text("preserve\\n", encoding="utf-8")
        link = output_dir / module.DELIVERY_ROOT_NAME
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Unsafe existing delivery root" in error for error in errors), errors
        assert link.is_symlink()
        assert marker.read_text(encoding="utf-8") == "preserve\\n"
        assert sorted(path.name for path in target.iterdir()) == ["marker.txt"]
    finally:
        td.cleanup()


'''
if new_tests not in test:
    if test.count(insert_before) != 1:
        raise SystemExit(f'expected one output-escape insertion point, found {test.count(insert_before)}')
    test = test.replace(insert_before, new_tests + insert_before, 1)
list_marker = '        test_source_commit_mismatch_blocks_release,\n'
list_add = '        test_unsafe_existing_delivery_root_fails_closed,\n        test_existing_delivery_root_symlink_fails_closed_when_supported,\n'
if list_add not in test:
    if test.count(list_marker) != 1:
        raise SystemExit(f'expected one tests-list insertion marker, found {test.count(list_marker)}')
    test = test.replace(list_marker, list_marker + list_add, 1)
test_path.write_text(test, encoding='utf-8')
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Delivery-root safety edit failed' }

    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed before safety commit' }
    git add project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { throw 'Delivery-root safety edit produced no staged changes' }
    git -c user.name='Malware Devil' -c user.email='34285973+malwaredevil@users.noreply.github.com' commit -m 'Fail closed on unsafe OpenAI delivery roots'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to commit delivery-root safety fix' }
    $testedSha = (git rev-parse HEAD).Trim()
    Write-Host "tested_branch_head=$testedSha"

    Invoke-Checked 'Compile combined release builder' { python -m py_compile project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py }
    Invoke-Checked 'Combined release self-tests' { python project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py }
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
    Invoke-Checked 'Exact-head combined deployment build' { python project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py --source-commit $testedSha --output-dir project_sources/validation/out_issue421_openai_delivery --parity-root project_sources/validation/out_issue421_openai_delivery/parity }
    Invoke-Checked 'Surface direct delivery artifact' { python .github/github_actions/tools/surface_delivery_zip.py --build-report project_sources/validation/out_issue421_openai_delivery/build_openai_gpt_deployment_release_report.json --output-dir project_sources/validation/out_issue421_openai_delivery/direct_artifact --manifest-dir project_sources/validation/out_issue421_openai_delivery/surface_manifest --extract-for-artifact --artifact-label dcoir-openai-gpt-deployment-packages --workflow-name manual-openai-gpt-deployment-package-build }

    @'
import json, zipfile
from pathlib import Path
root = Path('project_sources/validation/out_issue421_openai_delivery')
report = json.loads((root / 'build_openai_gpt_deployment_release_report.json').read_text(encoding='utf-8'))
if not report.get('success') or report.get('static_parity_status') != 'pass': raise SystemExit(f'combined release report not clean: {report}')
zip_path = Path(report['zip_path'])
with zipfile.ZipFile(zip_path) as zf: names = zf.namelist()
prefix = 'OpenAI_GPT_Deployment_Packages/'
if sum(name.startswith(prefix + 'AFRICOM_DCOIR_Analyst/Knowledge/') for name in names) != 7: raise SystemExit('DCOIR delivery Knowledge count is not seven')
if sum(name.startswith(prefix + 'AFRICOM_USB_Reporting/Knowledge/') for name in names) != 2: raise SystemExit('USB delivery Knowledge count is not two')
print(json.dumps({'success': True, 'zip_path': report['zip_path'], 'zip_sha256': report['zip_sha256'], 'entry_count': len(names)}, indent=2))
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Combined delivery ZIP inspection failed' }

    $tracked = git status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect tracked repository state' }
    if ($tracked) { $tracked | Out-Host; throw 'Validation changed tracked repository files' }
    git push origin HEAD:$branch
    if ($LASTEXITCODE -ne 0) { throw 'Push of validated issue #421 safety head failed' }
    Write-Host "validated_and_pushed_head=$testedSha"
  }
  finally { Pop-Location }
}
finally {
  git worktree remove --force $worktree 2>$null
  git worktree prune
}
