[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedBranch = 'issue-519-openrouter-run-telemetry'
$expectedHead = '6ba1e273c60f2d5fd22eb18ae3ad5bb6fa317ba4'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$remoteLine = (& git -C $repo ls-remote origin "refs/heads/$requestedBranch" | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "Could not resolve $requestedBranch" }
$remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
if ($remoteSha -ne $expectedHead) { throw "PR branch moved before GHAS fix: expected=$expectedHead actual=$remoteSha" }

$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr520-ghas-' + $expectedHead.Substring(0,12))
try {
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
    & git -C $repo fetch --no-tags origin $requestedBranch
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed: $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $remoteSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed: $LASTEXITCODE" }
    Set-Location -LiteralPath $worktree

    @(
        'OPENROUTER_API_KEY','DCOIR_OPENROUTER_API_KEY','OPENROUTER_MANAGEMENT_KEY',
        'OPENAI_API_KEY','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID',
        'DCOIR_GEMINI_API','DCOIR_GEMINI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY'
    ) | ForEach-Object { [Environment]::SetEnvironmentVariable($_, $null, 'Process') }
    $env:PYTHONDONTWRITEBYTECODE = '1'

    $patcher = Join-Path $env:RUNNER_TEMP 'patch_issue519_ghas.py'
    @'
from pathlib import Path

path = Path('.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py')
text = path.read_text(encoding='utf-8')

def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

replace_once(
    '''    try:\n        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)\n    except Exception:\n        pass\n''',
    '''    try:\n        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)\n    except Exception:\n        # Error accounting is advisory; never let it alter review behavior.\n        return\n''',
    'error accounting',
)
replace_once(
    '''                try:\n                    setattr(config, SUMMARY_ATTR, summary)\n                except Exception:\n                    pass\n''',
    '''                try:\n                    setattr(config, SUMMARY_ATTR, summary)\n                except Exception:\n                    # The bounded status message remains usable without persistence.\n                    _note_telemetry_error(config)\n''',
    'summary persistence',
)
replace_once(
    '''    try:\n        setattr(module, PATCH_ERRORS_ATTR, tuple(errors))\n    except Exception:\n        pass\n''',
    '''    try:\n        setattr(module, PATCH_ERRORS_ATTR, tuple(errors))\n    except Exception:\n        # Patch-error metadata is advisory and must not block module startup.\n        _note_telemetry_error(module)\n''',
    'patch error metadata',
)
replace_once(
    '''    try:\n        setattr(module, APPLIED_MARKER, True)\n    except Exception:\n        pass\n''',
    '''    try:\n        setattr(module, APPLIED_MARKER, True)\n    except Exception:\n        # Some proxy modules may reject attributes; review behavior still proceeds.\n        _note_telemetry_error(module)\n''',
    'applied marker',
)

path.write_text(text, encoding='utf-8')
'@ | Set-Content -LiteralPath $patcher -Encoding UTF8

    & python $patcher
    if ($LASTEXITCODE -ne 0) { throw "patcher failed: $LASTEXITCODE" }
    & python -m py_compile '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py' '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v54 py_compile failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v54 selftest failed' }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }

    $changed = @(& git status --porcelain=v1)
    if ($changed.Count -ne 1 -or $changed[0] -notmatch 'dcoir_review_required_runtime_patch_v54.py') { throw "Unexpected changed files: $($changed -join ', ')" }

    & git config user.name 'ChatGPT'
    & git config user.email 'noreply@openai.com'
    & git add -- '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py'
    & git commit -m 'Document fail-soft telemetry suppression'
    if ($LASTEXITCODE -ne 0) { throw "git commit failed: $LASTEXITCODE" }
    $newHead = (& git rev-parse HEAD).Trim()
    & git push origin "HEAD:refs/heads/$requestedBranch"
    if ($LASTEXITCODE -ne 0) { throw "git push failed: $LASTEXITCODE" }

    @{ schema='dcoir.issue519.pr520_ghas_empty_except_fix.v1'; previous_head=$expectedHead; new_head=$newHead; branch=$requestedBranch; py_compile='pass'; v54_selftest='pass'; git_diff_check='pass'; changed_files=1; inference_credentials_removed=$true; addressed_review_comment_ids=@(3971991769,3971991788,3971991799,3971991808) } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue519-pr520-ghas-empty-except-fix-v1-receipt.json') -Encoding utf8
    Write-Host "PR #520 GHAS empty-except fix pushed: $newHead"
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
