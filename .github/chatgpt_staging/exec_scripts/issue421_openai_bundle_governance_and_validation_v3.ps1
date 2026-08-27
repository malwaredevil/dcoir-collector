$ErrorActionPreference = 'Stop'

$sourceScript = '.github/chatgpt_staging/exec_scripts/issue421_openai_bundle_governance_and_validation_v2.ps1'
if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
  throw "Missing source validation script: $sourceScript"
}

$text = Get-Content -Raw -LiteralPath $sourceScript

$pythonMarker = "profiles_path = Path('.github/github_actions/workflow_required_surface_profiles.json')"
$pythonInsert = @'
audit_helper_path = Path('.github/github_actions/tools/lib/audit_reusable_contract_helpers.py')
audit_helper = audit_helper_path.read_text(encoding='utf-8')
old_primary_count = 'EXPECTED_PRIMARY_WORKFLOW_COUNT = 29'
if audit_helper.count(old_primary_count) != 1:
    raise SystemExit(f'expected one primary-workflow count constant, found {audit_helper.count(old_primary_count)}')
audit_helper = audit_helper.replace(old_primary_count, 'EXPECTED_PRIMARY_WORKFLOW_COUNT = 30', 1)
audit_helper_path.write_text(audit_helper, encoding='utf-8')

'@
if ($text.IndexOf($pythonMarker, [System.StringComparison]::Ordinal) -lt 0) {
  throw 'Unable to locate Python workflow-profile insertion marker in v2 script'
}
$text = $text.Replace($pythonMarker, $pythonInsert + $pythonMarker)

$gitAddNeedle = 'git add project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py .github/github_actions/workflow_required_surface_profiles.json'
$gitAddReplacement = 'git add project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py .github/github_actions/tools/lib/audit_reusable_contract_helpers.py .github/github_actions/workflow_required_surface_profiles.json'
if ($text.IndexOf($gitAddNeedle, [System.StringComparison]::Ordinal) -lt 0) {
  throw 'Unable to locate git-add insertion marker in v2 script'
}
$text = $text.Replace($gitAddNeedle, $gitAddReplacement)

$tempScript = Join-Path $env:RUNNER_TEMP 'issue421_openai_bundle_governance_and_validation_v3.generated.ps1'
Set-Content -LiteralPath $tempScript -Value $text -Encoding utf8
& $tempScript
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
