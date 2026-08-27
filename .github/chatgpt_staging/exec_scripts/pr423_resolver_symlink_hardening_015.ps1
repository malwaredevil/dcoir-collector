$ErrorActionPreference = 'Stop'
$source = '.github/chatgpt_staging/exec_scripts/pr423_resolver_symlink_hardening_014.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing source script: $source" }
$text = Get-Content -LiteralPath $source -Raw -Encoding UTF8
$badPayloadLine = '        (target_dir / "payload.txt").write_text("target\n", encoding="utf-8")' + "`n"
if (-not $text.Contains($badPayloadLine)) { throw 'Expected embedded payload-write line not found' }
$text = $text.Replace($badPayloadLine, '')
$oldPath = '            "linked-source/payload.txt",'
$newPath = '            "linked-source",'
if (-not $text.Contains($oldPath)) { throw 'Expected embedded linked-source path not found' }
$text = $text.Replace($oldPath, $newPath)
$tempScript = Join-Path $env:DCOIR_CONFIG_DIR 'pr423_resolver_symlink_hardening_015.expanded.ps1'
[IO.File]::WriteAllText($tempScript, $text, (New-Object System.Text.UTF8Encoding($false)))
& $tempScript
exit $LASTEXITCODE
