$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-010.ps1"
if (-not (Test-Path $sourceScript)) {
    throw "Expected source script not found: $sourceScript"
}

$script = Get-Content -Path $sourceScript -Raw
$anchor = '$script = $script.Replace($commitAnchor, ($gitIdentity + $commitAnchor))'
$replacement = @'
$script = $script.Replace($commitAnchor, ($gitIdentity + $commitAnchor))
$commitCommandAnchor = 'Invoke-Checked "git commit" { git commit -m "Fix OpenRouter redaction review gaps" }'
$preCommitAdd = "Invoke-Checked `"git add final`" { git add --all -- .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_codex_regression_selftest.py }`nInvoke-Checked `"git status after final add`" { git status --short }"
if (-not $script.Contains($commitCommandAnchor)) {
    throw "Commit command anchor not found in expanded script"
}
$script = $script.Replace($commitCommandAnchor, ($preCommitAdd + "`n" + $commitCommandAnchor))
'@
if (-not $script.Contains($anchor)) {
    throw "Assembly anchor not found in source script"
}
$script = $script.Replace($anchor, $replacement)

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260618-pr281-codex-p1-redaction-011-expanded.ps1"
Set-Content -Path $tempScript -Value $script -Encoding UTF8
& $tempScript
