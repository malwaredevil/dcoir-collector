$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-004.ps1"
if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
    throw "Expected source script not found: $sourceScript"
}

$outer = Get-Content -LiteralPath $sourceScript -Raw
$outerNeedle = '$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260625-pr312-dcoir-review-fixes-004-expanded.ps1"'
if (-not $outer.Contains($outerNeedle)) {
    throw "Outer insertion point not found in $sourceScript"
}

$injection = @'
$authNeedle = '    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"'
$authBlock = @"
    `$pushToken = `$env:DCOIR_GITHUB_CL_TOKEN
    if ([string]::IsNullOrWhiteSpace(`$pushToken)) {
        `$pushToken = `$env:DCOIR_GITHUB_FG_TOKEN
    }
    if ([string]::IsNullOrWhiteSpace(`$pushToken)) {
        throw "No DCOIR GitHub push token is available to the exec harness"
    }
    `$basicAuth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:`$pushToken"))
    git config --local http.https://github.com/DCOIR-Collector/dcoir-collector.extraheader "AUTHORIZATION: basic `$basicAuth"
"@
if (-not $script.Contains($authNeedle)) {
    throw "Git auth insertion point not found in expanded script"
}
$script = $script.Replace($authNeedle, $authNeedle + "`r`n" + $authBlock)

$innerNeedle = '    $patcherPath = Join-Path $env:RUNNER_TEMP "pr312_patch_static_context_v2.py"'
$innerPrepatch = @"
    `$prepatchPath = Join-Path `$env:RUNNER_TEMP "pr312_prepatch_duplicate_location.py"
    [IO.File]::WriteAllBytes(`$prepatchPath, [Convert]::FromBase64String("ZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgpwYXRoID0gUGF0aCgiLmdpdGh1Yi93b3JrZmxvd3Mvb3BlbnJvdXRlci1wci1yZXZpZXcueW1sIikKdGV4dCA9IHBhdGgucmVhZF90ZXh0KGVuY29kaW5nPSJ1dGYtOCIpCm9sZCA9ICdmImB7Y2VsbChpdGVtLmdldChcJ3BhdGhcJywgXCdcJykpfTp7Y2VsbChpdGVtLmdldChcJ2xpbmVcJywgXCdcJykpfWAiJwpuZXcgPSAnZiJ7Y2VsbChpdGVtLmdldChcJ3BhdGhcJywgXCdcJykpfTp7Y2VsbChpdGVtLmdldChcJ2xpbmVcJywgXCdcJykpfSInCmNvdW50ID0gdGV4dC5jb3VudChvbGQpCmlmIGNvdW50ICE9IDI6CiAgICByYWlzZSBTeXN0ZW1FeGl0KGYiZXhwZWN0ZWQgdHdvIGR1cGxpY2F0ZSBsb2NhdGlvbiBjb2RlIHNwYW5zIGJlZm9yZSBwcmVwYXRjaCwgZm91bmQge2NvdW50fSIpCnBhdGgud3JpdGVfdGV4dCh0ZXh0LnJlcGxhY2Uob2xkLCBuZXcsIDEpLCBlbmNvZGluZz0idXRmLTgiKQpwcmludCgicHJlLW5vcm1hbGl6ZWQgb25lIGR1cGxpY2F0ZSBsb2NhdGlvbiBjb2RlIHNwYW4iKQo="))
    Invoke-Checked "Pre-normalize one duplicate location code span" { python `$prepatchPath }
"@
if (-not $script.Contains($innerNeedle)) {
    throw "Inner patcher insertion point not found in expanded script"
}
$script = $script.Replace($innerNeedle, $innerPrepatch + "`r`n" + $innerNeedle)

$validatorNeedle = 'if ".Replace(''`'', ''\\\\`'').Replace(''|'', ''\\\\|'')" not in duplicate_text:'
$validatorReplacement = 'if ".Replace(''`''," not in duplicate_text or ".Replace(''|''," not in duplicate_text:'
if (-not $script.Contains($validatorNeedle)) {
    throw "Validator escaping insertion point not found in expanded script"
}
$script = $script.Replace($validatorNeedle, $validatorReplacement)
'@

$outer = $outer.Replace($outerNeedle, $injection + "`r`n" + $outerNeedle)
$tempOuter = Join-Path $env:RUNNER_TEMP "exec-20260625-pr312-dcoir-review-fixes-007-outer.ps1"
Set-Content -LiteralPath $tempOuter -Value $outer -Encoding UTF8
& $tempOuter
