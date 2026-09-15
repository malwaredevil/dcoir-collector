$ErrorActionPreference = 'Stop'
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
$sourcePath = Join-Path $repo '.github/chatgpt_staging/exec_scripts/issue550-pr553-function-ownership-audit-001.ps1'
$innerPath = Join-Path $downloads 'issue550-pr553-function-ownership-audit-002-inner.ps1'
$source = [IO.File]::ReadAllText($sourcePath)
$replacements = [ordered]@{
  '781a480bb306ff7e0bf1fd55302636a0176ad5c5' = 'f10aa75bbdf54110329409371d7aa86404b6ba65'
  'ecfe9870cff993695d58c9ee8f35525a0ccd9902' = '91021d85eec18569fe52492c13959cd8b28a0331'
  'issue550-pr553-function-ownership-audit-001' = 'issue550-pr553-function-ownership-audit-002'
  'ISSUE550_PR553_FUNCTION_OWNERSHIP_AUDIT_001_PASS' = 'ISSUE550_PR553_FUNCTION_OWNERSHIP_AUDIT_002_PASS'
}
foreach ($key in $replacements.Keys) {
  if (-not $source.Contains($key)) { throw "Missing ownership-audit replacement anchor: $key" }
  $source = $source.Replace($key, $replacements[$key])
}
[IO.File]::WriteAllText($innerPath, $source, [Text.UTF8Encoding]::new($false))
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $innerPath
if ($LASTEXITCODE -ne 0) { throw "Ownership audit inner script failed with exit code $LASTEXITCODE" }
Write-Host 'FUNCTION_OWNERSHIP_AUDIT_002_WRAPPER_PASS'
