$ErrorActionPreference = 'Stop'

$branch = 'issue-421-openai-gpt-deployment-builder'
$expectedHead = '1138588ff57be1c250e9b84c50736b204695a7d7'
$worktree = Join-Path $env:RUNNER_TEMP 'issue421-dcoir-path-hardening'

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

marker = '''def _resolve_repo_path(repo_root: Path, relative: str | Path, errors: list[str], label: str) -> Path | None:
    return _resolve_inside(repo_root, relative, errors, label)


def _source_commit(repo_root: Path, explicit: str | None) -> str:
'''
replacement = '''def _resolve_repo_path(repo_root: Path, relative: str | Path, errors: list[str], label: str) -> Path | None:
    return _resolve_inside(repo_root, relative, errors, label)


def _validate_output_path(
    root: Path,
    destination: Path,
    errors: list[str],
    label: str,
) -> Path | None:
    try:
        resolved_root = root.resolve()
        resolved_parent = destination.parent.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        errors.append(f"{label} could not be resolved safely: {type(exc).__name__}: {exc}")
        return None
    if not resolved_parent.is_relative_to(resolved_root):
        errors.append(f"{label} escapes its allowed output root: {destination.as_posix()}")
        return None
    if destination.is_symlink():
        errors.append(f"{label} must not be a symlink: {destination.as_posix()}")
        return None
    if destination.exists() and not destination.is_file():
        errors.append(f"{label} must be a regular file or absent: {destination.as_posix()}")
        return None
    return destination


def _write_output_bytes(
    root: Path,
    destination: Path,
    data: bytes,
    errors: list[str],
    label: str,
) -> bool:
    safe_destination = _validate_output_path(root, destination, errors, label)
    if safe_destination is None:
        return False
    safe_destination.parent.mkdir(parents=True, exist_ok=True)
    safe_destination.write_bytes(data)
    return True


def _source_commit(repo_root: Path, explicit: str | None) -> str:
'''
if builder.count(marker) != 1:
    raise SystemExit(f'expected one output-helper insertion marker, found {builder.count(marker)}')
builder = builder.replace(marker, replacement, 1)

old_copy = '''def _copy_record(
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
new_copy = '''def _copy_record(
    source: Path,
    destination: Path,
    delivery_root: Path,
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    data = source.read_bytes()
    if not _write_output_bytes(
        delivery_root,
        destination,
        data,
        errors,
        "delivery file",
    ):
        return None
    return {
        "delivery_path": destination.relative_to(delivery_root).as_posix(),
        "source_path": source.relative_to(repo_root).as_posix(),
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
    }
'''
if builder.count(old_copy) != 1:
    raise SystemExit(f'expected one _copy_record block, found {builder.count(old_copy)}')
builder = builder.replace(old_copy, new_copy, 1)

old_package = '''        file_records.append(_copy_record(source, destination_root / name, delivery_root, repo_root))
'''
new_package = '''        record = _copy_record(
            source,
            destination_root / name,
            delivery_root,
            repo_root,
            errors,
        )
        if record is not None:
            file_records.append(record)
'''
if builder.count(old_package) != 1:
    raise SystemExit(f'expected one package copy call, found {builder.count(old_package)}')
builder = builder.replace(old_package, new_package, 1)

old_knowledge = '''        record = _copy_record(source, destination_root / "Knowledge" / source.name, delivery_root, repo_root)
        record.update({"id": item.get("id"), "order": item.get("order")})
        knowledge_records.append(record)
'''
new_knowledge = '''        record = _copy_record(
            source,
            destination_root / "Knowledge" / source.name,
            delivery_root,
            repo_root,
            errors,
        )
        if record is not None:
            record.update({"id": item.get("id"), "order": item.get("order")})
            knowledge_records.append(record)
'''
if builder.count(old_knowledge) != 1:
    raise SystemExit(f'expected one knowledge copy block, found {builder.count(old_knowledge)}')
builder = builder.replace(old_knowledge, new_knowledge, 1)

old_output_start = '''    output_dir.mkdir(parents=True, exist_ok=True)

    parity_json_path = parity_root / PARITY_JSON
'''
new_output_start = '''    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "build_openai_gpt_deployment_release_report.json"
    zip_name = f"DCOIR_OpenAI_GPT_Deployment_Packages_{commit[:12] if commit != 'unknown' else 'unknown'}.zip"
    zip_path = output_dir / zip_name
    _validate_output_path(output_dir, report_path, errors, "build report")
    _validate_output_path(output_dir, zip_path, errors, "delivery ZIP")
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

    parity_json_path = parity_root / PARITY_JSON
'''
if builder.count(old_output_start) != 1:
    raise SystemExit(f'expected one output start block, found {builder.count(old_output_start)}')
builder = builder.replace(old_output_start, new_output_start, 1)

old_evidence = '''    if guide_path is not None and guide_path.is_file():
        _copy_record(guide_path, delivery_root / GUIDE.name, delivery_root, repo_root)
    if parity_json_path.is_file():
        _copy_record(parity_json_path, delivery_root / PARITY_JSON, delivery_root, repo_root)
    if parity_md_path.is_file():
        _copy_record(parity_md_path, delivery_root / PARITY_MD, delivery_root, repo_root)
'''
new_evidence = '''    if guide_path is not None and guide_path.is_file():
        _copy_record(guide_path, delivery_root / GUIDE.name, delivery_root, repo_root, errors)
    if parity_json_path.is_file():
        _copy_record(parity_json_path, delivery_root / PARITY_JSON, delivery_root, repo_root, errors)
    if parity_md_path.is_file():
        _copy_record(parity_md_path, delivery_root / PARITY_MD, delivery_root, repo_root, errors)
'''
if builder.count(old_evidence) != 1:
    raise SystemExit(f'expected one evidence copy block, found {builder.count(old_evidence)}')
builder = builder.replace(old_evidence, new_evidence, 1)

old_manifest = '''    (delivery_root / "delivery_manifest.json").write_bytes(_json_bytes(manifest))
    (delivery_root / "delivery_manifest.md").write_text(
        _delivery_markdown(manifest), encoding="utf-8"
    )

    zip_name = f"DCOIR_OpenAI_GPT_Deployment_Packages_{commit[:12] if commit != 'unknown' else 'unknown'}.zip"
    zip_path = output_dir / zip_name
    if zip_path.exists():
        zip_path.unlink()
'''
new_manifest = '''    _write_output_bytes(
        delivery_root,
        delivery_root / "delivery_manifest.json",
        _json_bytes(manifest),
        errors,
        "delivery manifest JSON",
    )
    _write_output_bytes(
        delivery_root,
        delivery_root / "delivery_manifest.md",
        _delivery_markdown(manifest).encode("utf-8"),
        errors,
        "delivery manifest Markdown",
    )

    if zip_path.exists():
        zip_path.unlink()
'''
if builder.count(old_manifest) != 1:
    raise SystemExit(f'expected one manifest/zip block, found {builder.count(old_manifest)}')
builder = builder.replace(old_manifest, new_manifest, 1)

old_report = '''    report_path = output_dir / "build_openai_gpt_deployment_release_report.json"
    report_path.write_bytes(_json_bytes(report))
    return errors, report
'''
new_report = '''    if not _write_output_bytes(
        output_dir,
        report_path,
        _json_bytes(report),
        errors,
        "build report",
    ):
        report["success"] = False
        report["errors"] = errors
    return errors, report
'''
if builder.count(old_report) != 1:
    raise SystemExit(f'expected one report write block, found {builder.count(old_report)}')
builder = builder.replace(old_report, new_report, 1)

builder_path.write_text(builder, encoding='utf-8')

test_path = Path('project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py')
test = test_path.read_text(encoding='utf-8')
insert_before = 'def test_output_escape_is_rejected() -> None:\n'
new_tests = '''def test_copy_record_rejects_destination_escape() -> None:
    td, repo = stage_repo()
    try:
        delivery_root = repo / "project_sources/validation/delivery"
        delivery_root.mkdir(parents=True, exist_ok=True)
        source = repo / "source.txt"
        source.write_text("source\\n", encoding="utf-8")
        outside = repo / "project_sources/validation/outside.txt"
        errors: list[str] = []
        record = module._copy_record(
            source,
            outside,
            delivery_root,
            repo,
            errors,
        )
        assert record is None
        assert errors
        assert any("escapes its allowed output root" in error for error in errors), errors
        assert not outside.exists()
    finally:
        td.cleanup()


def test_existing_report_output_directory_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "build_openai_gpt_deployment_release_report.json"
        report_path.mkdir()
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("build report must be a regular file or absent" in error for error in errors), errors
        assert report_path.is_dir()
        assert not (output_dir / module.DELIVERY_ROOT_NAME).exists()
    finally:
        td.cleanup()


def test_existing_zip_output_directory_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_name = f"DCOIR_OpenAI_GPT_Deployment_Packages_{SOURCE_COMMIT[:12]}.zip"
        zip_path = output_dir / zip_name
        zip_path.mkdir()
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("delivery ZIP must be a regular file or absent" in error for error in errors), errors
        assert zip_path.is_dir()
        assert not (output_dir / module.DELIVERY_ROOT_NAME).exists()
    finally:
        td.cleanup()


def test_output_leaf_symlink_fails_closed_when_supported() -> None:
    td, repo = stage_repo()
    try:
        root = repo / "project_sources/validation/out"
        root.mkdir(parents=True, exist_ok=True)
        target = repo / "project_sources/validation/target.txt"
        target.write_text("preserve\\n", encoding="utf-8")
        link = root / "report.json"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return
        errors: list[str] = []
        safe = module._validate_output_path(root, link, errors, "test output")
        assert safe is None
        assert any("must not be a symlink" in error for error in errors), errors
        assert target.read_text(encoding="utf-8") == "preserve\\n"
    finally:
        td.cleanup()


'''
if test.count(insert_before) != 1:
    raise SystemExit(f'expected one self-test insertion point, found {test.count(insert_before)}')
test = test.replace(insert_before, new_tests + insert_before, 1)
list_marker = '        test_existing_delivery_root_symlink_fails_closed_when_supported,\n'
list_add = '''        test_copy_record_rejects_destination_escape,
        test_existing_report_output_directory_fails_closed,
        test_existing_zip_output_directory_fails_closed,
        test_output_leaf_symlink_fails_closed_when_supported,
'''
if test.count(list_marker) != 1:
    raise SystemExit(f'expected one self-test list marker, found {test.count(list_marker)}')
test = test.replace(list_marker, list_marker + list_add, 1)
test_path.write_text(test, encoding='utf-8')
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'DCOIR path-hardening edit failed' }

    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed before hardening commit' }
    git add project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { throw 'DCOIR path-hardening edit produced no staged changes' }
    git -c user.name='Malware Devil' -c user.email='34285973+malwaredevil@users.noreply.github.com' commit -m 'Harden OpenAI deployment output paths'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to commit DCOIR path-hardening fix' }
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
    Invoke-Checked '10 OpenAI USB package self-tests' { python project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py }
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
if len(names) != 20: raise SystemExit(f'unexpected ZIP entry count: {len(names)}')
print(json.dumps({'success': True, 'zip_path': report['zip_path'], 'zip_sha256': report['zip_sha256'], 'entry_count': len(names)}, indent=2))
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Combined delivery ZIP inspection failed' }

    $tracked = git status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect tracked repository state' }
    if ($tracked) { $tracked | Out-Host; throw 'Validation changed tracked repository files' }
    git push origin HEAD:$branch
    if ($LASTEXITCODE -ne 0) { throw 'Push of validated issue #421 hardening head failed' }
    Write-Host "validated_and_pushed_head=$testedSha"
  }
  finally { Pop-Location }
}
finally {
  git worktree remove --force $worktree 2>$null
  git worktree prune
}
