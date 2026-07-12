$ErrorActionPreference = 'Stop'
$repo = $env:DCOIR_REPO_ROOT
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is not set' }
Set-Location $repo

git config user.name 'chatgpt-exec'
git config user.email 'chatgpt-exec@users.noreply.github.com'
git pull --ff-only origin main

$manifestPath = 'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/prime_agent_chunks/Prime_Agent_Chunks_Manifest.json'
$old = '"expected_sha256": "18f9b9ee53cf5a5c9d2676025331a4d0ce75a23bce1afa154bf750545680f8cc"'
$new = '"expected_sha256": "30f5de55995bb2d895bfbe5029a3e8faaf3d21147efc7421a76c1f44adcfb4c5"'
$text = Get-Content -LiteralPath $manifestPath -Raw
if ($text -notlike "*$old*") { throw 'Expected stale reassembly checksum was not found.' }
$text = $text.Replace($old, $new)
Set-Content -LiteralPath $manifestPath -Value $text -Encoding utf8NoBOM

git add -- $manifestPath
if (git diff --cached --quiet) {
  Write-Host 'No checksum change to commit.'
} else {
  git commit -m 'Update Gemini prime chunk reassembly checksum'
  git push origin HEAD:main
}

$statusAfter = git status --porcelain
if ($statusAfter) { throw "Worktree is not clean after checksum update: $($statusAfter -join '; ')" }
