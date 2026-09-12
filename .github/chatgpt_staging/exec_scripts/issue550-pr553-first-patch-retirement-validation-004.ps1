$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'issue550-pr553-first-patch-retirement-validation-003.ps1'
if (-not (Test-Path -LiteralPath $source)) { throw 'Validation template 003 is unavailable' }
$runnerTemp = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$temp = Join-Path $runnerTemp ('issue550-pr553-first-patch-retirement-validation-004-' + [Guid]::NewGuid().ToString('N') + '.ps1')
$text = Get-Content -LiteralPath $source -Raw
$text = $text.Replace('fc8c400ae0991728687a2797d40cf361dba8839d', 'a94ccfec6171df57da77c839466a67a092ee9139')
$text = $text.Replace('issue550-pr553-first-patch-retirement-validation-003.json', 'issue550-pr553-first-patch-retirement-validation-004.json')
$text | Out-File -FilePath $temp -Encoding utf8
try {
    & $temp
}
finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
