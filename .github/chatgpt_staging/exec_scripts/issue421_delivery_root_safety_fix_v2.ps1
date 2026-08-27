$ErrorActionPreference = 'Stop'

$sourceScript = '.github/chatgpt_staging/exec_scripts/issue421_delivery_root_safety_fix.ps1'
if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
  throw "Missing source safety script: $sourceScript"
}
$text = Get-Content -Raw -LiteralPath $sourceScript
$oldHead = "`$expectedHead = 'f8fd3a4637b75e5268b0380bfeac00fdda62b8fe'"
$newHead = "`$expectedHead = 'c7325f802f414c6a662623e846a823902c3739ea'"
if ($text.IndexOf($oldHead, [System.StringComparison]::Ordinal) -lt 0) {
  throw 'Unable to locate expected-head marker in source safety script'
}
$text = $text.Replace($oldHead, $newHead)
$tempScript = Join-Path $env:RUNNER_TEMP 'issue421_delivery_root_safety_fix_v2.generated.ps1'
Set-Content -LiteralPath $tempScript -Value $text -Encoding utf8
& $tempScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
