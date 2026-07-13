$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ExpectedHead = "94759784627f546c3ae30b3a5521fc59a1925a50"
$PrBranch = "implement-pr-review-command-workflow"
$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1"
if (-not (Test-Path $sourceScript)) {
    throw "Expected source script not found: $sourceScript"
}

function Invoke-NativeChecked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        if ($output) {
            $output | Write-Output
        }
        throw "$Description failed with exit code $exitCode"
    }
    if ($output) {
        $output | Write-Output
    }
}

Invoke-NativeChecked "git fetch PR branch" { git fetch --quiet origin $PrBranch }
$currentHead = (git rev-parse FETCH_HEAD).Trim()
if ($currentHead -ne $ExpectedHead) {
    throw "Unexpected PR branch head. Expected $ExpectedHead but found $currentHead"
}

$workDir = Join-Path $env:RUNNER_TEMP "pr281-redaction-worktree"
if (Test-Path $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}
Invoke-NativeChecked "git worktree add PR head" { git worktree add --detach $workDir $ExpectedHead }

$script = Get-Content -Path $sourceScript -Raw
$script = $script.Replace('$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"')
$script = $script.Replace('git fetch origin $PrBranch', 'git fetch --quiet origin $PrBranch')

$badRegression = @'
curl_user_continuation = "curl --user " + "\\" + "\n  \"dcoir:continued curl secret 12345\" https://example.test/"
cleaned_curl_user = sanitized(curl_user_continuation)
assert "continued curl secret 12345" not in cleaned_curl_user, cleaned_curl_user
assert "dcoir:[redacted-secret]" in cleaned_curl_user, cleaned_curl_user

curl_proxy_continuation = "curl --proxy-user " + "\\" + "\n  'proxy:continued proxy secret 12345' https://example.test/"
cleaned_curl_proxy = sanitized(curl_proxy_continuation)
assert "continued proxy secret 12345" not in cleaned_curl_proxy, cleaned_curl_proxy
assert "proxy:[redacted-secret]" in cleaned_curl_proxy, cleaned_curl_proxy

curl_short_continuation = "curl -u" + "\\" + "\n  dcoir:continued-short-option-secret-12345 https://example.test/"
cleaned_curl_short = sanitized(curl_short_continuation)
assert "continued-short-option-secret-12345" not in cleaned_curl_short, cleaned_curl_short
assert "dcoir:[redacted-secret]" in cleaned_curl_short, cleaned_curl_short
'@
$goodRegression = @'
line_continuation = chr(92) + chr(10)

curl_user_continuation = 'curl --user ' + line_continuation + '  "dcoir:continued curl secret 12345" https://example.test/'
cleaned_curl_user = sanitized(curl_user_continuation)
assert "continued curl secret 12345" not in cleaned_curl_user, cleaned_curl_user
assert "dcoir:[redacted-secret]" in cleaned_curl_user, cleaned_curl_user

curl_proxy_continuation = "curl --proxy-user " + line_continuation + "  'proxy:continued proxy secret 12345' https://example.test/"
cleaned_curl_proxy = sanitized(curl_proxy_continuation)
assert "continued proxy secret 12345" not in cleaned_curl_proxy, cleaned_curl_proxy
assert "proxy:[redacted-secret]" in cleaned_curl_proxy, cleaned_curl_proxy

curl_short_continuation = "curl -u" + line_continuation + "  dcoir:continued-short-option-secret-12345 https://example.test/"
cleaned_curl_short = sanitized(curl_short_continuation)
assert "continued-short-option-secret-12345" not in cleaned_curl_short, cleaned_curl_short
assert "dcoir:[redacted-secret]" in cleaned_curl_short, cleaned_curl_short
'@
if (-not $script.Contains($badRegression)) {
    throw "Regression replacement anchor not found in source script"
}
$script = $script.Replace($badRegression, $goodRegression)

$commitAnchor = 'Invoke-Checked "git add" { git add .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_codex_regression_selftest.py }'
$gitIdentity = @'
Invoke-Checked "git configure user email" { git config user.email "chatgpt-exec@users.noreply.github.com" }
Invoke-Checked "git configure user name" { git config user.name "ChatGPT Exec" }
'@
if (-not $script.Contains($commitAnchor)) {
    throw "Commit anchor not found in source script"
}
$script = $script.Replace($commitAnchor, ($gitIdentity + $commitAnchor))

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260618-pr281-codex-p1-redaction-006-expanded.ps1"
Set-Content -Path $tempScript -Value $script -Encoding UTF8

Push-Location $workDir
try {
    & $tempScript
} finally {
    Pop-Location
}
