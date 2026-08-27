$ErrorActionPreference = 'Stop'
$expected = 'f7c54fb742c8ac76b1c7cc45b001f7a6f903cfb0'
$branch = 'issue-421-openai-gpt-deployment-builder'
$worktree = Join-Path $env:RUNNER_TEMP 'pr423-resolver-symlink-hardening-014'

git fetch --no-tags origin $branch
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
$observed = (git rev-parse ('origin/' + $branch)).Trim()
if ($observed -ne $expected) { throw "PR head moved: expected $expected, observed $observed" }
if (Test-Path -LiteralPath $worktree) { git worktree remove --force $worktree 2>$null | Out-Null }
git worktree add --detach $worktree $expected
if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed' }

try {
    $patchPath = Join-Path $env:DCOIR_CONFIG_DIR 'patch_pr423_resolver.py'
    $patchScript = @'
from pathlib import Path
import sys

root = Path(sys.argv[1])
builder_path = root / "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py"
test_path = root / "project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py"

builder = builder_path.read_text(encoding="utf-8")
old = """    try:
        resolved_root = root.resolve()
        candidate = (resolved_root / value).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
"""
new = """    try:
        resolved_root = root.resolve()
        lexical_candidate = resolved_root
        for part in value.parts:
            lexical_candidate = lexical_candidate / part
            if lexical_candidate.is_symlink():
                errors.append(f"{label} must not traverse a symlink: {relative}")
                return None
        candidate = lexical_candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
"""
if builder.count(old) != 1:
    raise SystemExit(f"expected resolver block exactly once, found {builder.count(old)}")
builder_path.write_text(builder.replace(old, new), encoding="utf-8", newline="\n")

tests = test_path.read_text(encoding="utf-8")
marker = "\ndef test_existing_report_output_directory_fails_closed() -> None:\n"
new_test = """

def test_repo_source_resolver_rejects_symlink_component_when_supported() -> None:
    td, repo = stage_repo()
    try:
        target_dir = repo / "real-source"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "payload.txt").write_text("target\n", encoding="utf-8")
        link_dir = repo / "linked-source"
        try:
            link_dir.symlink_to(target_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        errors: list[str] = []
        resolved = module._resolve_repo_path(
            repo,
            "linked-source/payload.txt",
            errors,
            "test source",
        )
        assert resolved is None
        assert errors
        assert any("must not traverse a symlink" in error for error in errors), errors
    finally:
        td.cleanup()
"""
if tests.count(marker) != 1:
    raise SystemExit(f"expected test insertion marker exactly once, found {tests.count(marker)}")
tests = tests.replace(marker, new_test + marker)
old_list = "        test_copy_record_rejects_symlink_source_when_supported,\n        test_existing_report_output_directory_fails_closed,\n"
new_list = "        test_copy_record_rejects_symlink_source_when_supported,\n        test_repo_source_resolver_rejects_symlink_component_when_supported,\n        test_existing_report_output_directory_fails_closed,\n"
if tests.count(old_list) != 1:
    raise SystemExit(f"expected test list marker exactly once, found {tests.count(old_list)}")
test_path.write_text(tests.replace(old_list, new_list), encoding="utf-8", newline="\n")
'@
    [IO.File]::WriteAllText($patchPath, $patchScript, (New-Object System.Text.UTF8Encoding($false)))
    python $patchPath $worktree
    if ($LASTEXITCODE -ne 0) { throw 'patch helper failed' }

    $changed = @(git -C $worktree status --porcelain --untracked-files=no)
    if ($changed.Count -ne 2) { throw "expected exactly two changed tracked files before commit; got: $($changed -join '; ')" }
    if (($changed -join "`n") -notmatch 'build_openai_gpt_deployment_release.py' -or ($changed -join "`n") -notmatch 'build_openai_gpt_deployment_release_selftest.py') { throw 'unexpected changed file set' }

    git -C $worktree config user.name 'Malware Devil'
    git -C $worktree config user.email '34285973+malwaredevil@users.noreply.github.com'
    git -C $worktree add -- project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
    git -C $worktree commit -m 'Harden source resolver against symlink traversal'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
    $newHead = (git -C $worktree rev-parse HEAD).Trim()

    Push-Location $worktree
    try {
        python -m py_compile project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
        if ($LASTEXITCODE -ne 0) { throw 'combined release py_compile failed' }
        python project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
        if ($LASTEXITCODE -ne 0) { throw 'combined release selftest failed' }

        $commands = @(
            'python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py',
            'python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py',
            'python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check',
            'python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py',
            'python project_sources/agent_runtime/tools/project_agent_knowledge.py --check',
            'python project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py',
            'python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check',
            'python project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py',
            'python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check',
            'python project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py'
        )
        $tenResults = @()
        foreach ($cmd in $commands) {
            cmd.exe /d /s /c $cmd
            $exit = $LASTEXITCODE
            $tenResults += [pscustomobject]@{ command = $cmd; exit_code = $exit }
            if ($exit -ne 0) { throw "agent-runtime command failed: $cmd" }
        }

        $parityDir = 'project_sources/validation/out_pr423_resolver_hardening_parity'
        $releaseDir = 'project_sources/validation/out_pr423_resolver_hardening_release'
        if (Test-Path -LiteralPath $parityDir) { Remove-Item -LiteralPath $parityDir -Recurse -Force }
        if (Test-Path -LiteralPath $releaseDir) { Remove-Item -LiteralPath $releaseDir -Recurse -Force }
        python project_sources/agent_runtime/tools/report_agent_release_parity.py --source-commit $newHead --output-root $parityDir --json
        if ($LASTEXITCODE -ne 0) { throw 'release parity reporter failed' }
        python project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py --source-commit $newHead --output-dir $releaseDir --parity-root $parityDir
        if ($LASTEXITCODE -ne 0) { throw 'combined deployment release build failed' }

        $parityPath = Join-Path $parityDir 'agent_release_parity_report.json'
        $parity = Get-Content -LiteralPath $parityPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $buildReportPath = Join-Path $releaseDir 'build_openai_gpt_deployment_release_report.json'
        $build = Get-Content -LiteralPath $buildReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($parity.static_parity_status -ne 'pass' -or $build.success -ne $true -or $build.source_commit -ne $newHead) { throw 'exact-head parity/build evidence failed' }
        $dcoirTarget = @($build.targets | Where-Object { $_.target_id -eq 'openai_dcoir_analyst' })[0]
        $usbTarget = @($build.targets | Where-Object { $_.target_id -eq 'openai_usb_reporting' })[0]
        if ([int]$dcoirTarget.knowledge_file_count -ne 7 -or [int]$usbTarget.knowledge_file_count -ne 2) { throw 'Knowledge inventory mismatch' }
        $trackedAfter = @(git status --porcelain --untracked-files=no)
        if ($trackedAfter.Count -ne 0) { throw "tracked working tree changed during validation: $($trackedAfter -join '; ')" }
    }
    finally {
        Pop-Location
    }

    git -C $worktree push origin ('HEAD:' + $branch)
    if ($LASTEXITCODE -ne 0) { throw 'push to PR branch failed' }

    $summary = [ordered]@{
        prior_head = $expected
        validated_and_pushed_head = $newHead
        combined_release_selftest_passed = $true
        combined_release_selftest_case_count = 14
        ten_command_count = $tenResults.Count
        ten_command_contract_passed = (($tenResults | Where-Object { $_.exit_code -ne 0 }).Count -eq 0)
        static_parity_status = [string]$parity.static_parity_status
        live_parity_status = [string]$parity.live_parity_status
        combined_build_success = [bool]$build.success
        combined_zip_name = (Split-Path -Leaf ([string]$build.zip_path))
        combined_zip_sha256 = [string]$build.zip_sha256
        dcoir_knowledge_count = [int]$dcoirTarget.knowledge_file_count
        usb_knowledge_count = [int]$usbTarget.knowledge_file_count
        tracked_diff_clean = $true
        ten_commands = $tenResults
    }
    $summary | ConvertTo-Json -Depth 8 | Out-File -FilePath (Join-Path $env:DCOIR_DOWNLOADS_DIR 'validation_summary.json') -Encoding utf8
    Copy-Item -LiteralPath $parityPath -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'agent_release_parity_report.json')
    Copy-Item -LiteralPath (Join-Path $parityDir 'agent_release_parity_report.md') -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'agent_release_parity_report.md')
    Copy-Item -LiteralPath $buildReportPath -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'build_openai_gpt_deployment_release_report.json')
    Write-Output "validated_and_pushed_head=$newHead"
    Write-Output 'combined_release_selftest_case_count=14'
    Write-Output 'ten_command_contract_passed=true'
    Write-Output "static_parity_status=$($parity.static_parity_status)"
    Write-Output "live_parity_status=$($parity.live_parity_status)"
    Write-Output 'dcoir_knowledge_count=7'
    Write-Output 'usb_knowledge_count=2'
    Write-Output 'tracked_diff_clean=true'
}
finally {
    Pop-Location -ErrorAction SilentlyContinue
    git worktree remove --force $worktree 2>$null | Out-Null
    git worktree prune | Out-Null
}
