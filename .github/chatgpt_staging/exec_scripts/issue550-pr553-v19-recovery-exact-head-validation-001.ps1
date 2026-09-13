$ErrorActionPreference = 'Stop'

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }

$sourceRel = '.github/chatgpt_staging/exec_scripts/issue550-pr553-v19-precision-guard-validation-001.ps1'
$sourcePath = Join-Path $repo $sourceRel
if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Missing validated source harness: $sourceRel" }
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash.ToLowerInvariant()
$expectedSourceHash = '9e0fa38f5feaf87a78cd5a6b4c3d34ad175bd36c'
# Git blob SHA and file SHA-256 are different identifiers; require the immutable Git blob below instead.
$blob = (& git -C $repo hash-object -- $sourceRel).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to hash source harness as Git blob' }
if ($blob -ne '9e0fa38f5feaf87a78cd5a6b4c3d34ad175bd36c') { throw "Unexpected source harness Git blob: $blob" }

$text = Get-Content -Raw -LiteralPath $sourcePath
$text = $text.Replace('9b7d3d35bfac3b99d7ed09a5be640deb398dcbf4','f57eab7464beb601ce350833a6152e5b6d77b20e')
$text = $text.Replace('issue550-pr553-v19-precision-guard-validation-001','issue550-pr553-v19-recovery-exact-head-validation-001')
$text = $text.Replace('ISSUE550_PR553_V19_PRECISION_GUARD_VALIDATION_001_PASS','ISSUE550_PR553_V19_RECOVERY_EXACT_HEAD_VALIDATION_001_PASS')
if ($text -notmatch "\$expectedHead = 'f57eab7464beb601ce350833a6152e5b6d77b20e'") { throw 'Expected-head substitution failed' }
if ($text -notmatch 'issue550-pr553-v19-recovery-exact-head-validation-001') { throw 'Request-id substitution failed' }
if ($text -notmatch 'ISSUE550_PR553_V19_RECOVERY_EXACT_HEAD_VALIDATION_001_PASS') { throw 'Terminal-marker substitution failed' }

$temp = Join-Path ([IO.Path]::GetTempPath()) ('issue550-pr553-v19-recovery-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    [IO.File]::WriteAllText($temp, $text, [Text.UTF8Encoding]::new($false))
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $temp
    if ($LASTEXITCODE -ne 0) { throw "Recovery exact-head validation failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
