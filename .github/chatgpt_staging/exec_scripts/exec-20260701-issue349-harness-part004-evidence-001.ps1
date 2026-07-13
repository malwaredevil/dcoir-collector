$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$RequestId = 'exec-20260701-issue349-harness-part004-evidence-001'
$TargetBranch = 'codex/349-workflow-file-modularization'
$ExpectedHead = '51baee007cf4c66bbd95fe849f349ddabf817a89'
$MainBranch = $env:GITHUB_REF_NAME
if ([string]::IsNullOrWhiteSpace($MainBranch)) {
    $MainBranch = 'main'
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Description,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    Write-Host "==> $Description"
    $output = & $Command 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($output) {
        $output | Write-Output
    }
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode"
    }
}

function Invoke-PythonBlock {
    param(
        [Parameter(Mandatory=$true)][string]$Description,
        [Parameter(Mandatory=$true)][string]$Code
    )
    $scriptPath = Join-Path $env:RUNNER_TEMP ($Description -replace '[^A-Za-z0-9._-]', '_')
    $scriptPath = "$scriptPath.py"
    Set-Content -LiteralPath $scriptPath -Value $Code -Encoding UTF8
    Invoke-Checked $Description { python $scriptPath }
}

$switchedToTarget = $false
$summaryData = $null

try {
    git config user.name 'github-actions[bot]'
    git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
    git config core.autocrlf false
    git config core.eol lf
    git config core.longpaths true

    Invoke-Checked 'Fetch target PR branch' { git fetch --no-tags origin "refs/heads/$TargetBranch`:refs/remotes/origin/$TargetBranch" }
    $ActualHead = (git rev-parse "origin/$TargetBranch").Trim()
    if ($ActualHead -ne $ExpectedHead) {
        throw "Target branch head mismatch. Expected $ExpectedHead but found $ActualHead."
    }

    Invoke-Checked 'Checkout target PR branch head' { git checkout -B issue349-harness-part004-evidence-refresh "origin/$TargetBranch" }
    $switchedToTarget = $true

    $updateCode = @'
from pathlib import Path
import json

repo = Path(".").resolve()
profiles_path = repo / ".github/github_actions/workflow_required_surface_profiles.json"
profiles = json.loads(profiles_path.read_text(encoding="utf-8"))

p14 = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-014.ps1.txt"
p15 = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-015.ps1.txt"
p16 = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-016.ps1.txt"
updated_profiles = []
for name, value in profiles.items():
    if isinstance(value, list) and p14 in value:
        value = [entry for entry in value if entry not in {p15, p16}]
        insert_at = value.index(p14) + 1
        value[insert_at:insert_at] = [p15, p16]
        profiles[name] = value
        updated_profiles.append(name)

expected_profile_count = 5
if len(updated_profiles) != expected_profile_count:
    raise SystemExit(f"expected {expected_profile_count} harness profiles to update, updated {updated_profiles}")

profiles_path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")

test_path = repo / "project_sources/collector/tools/powershell_assembly_parity_test_real_repo.py"
test_text = test_path.read_text(encoding="utf-8")
old = 'self.assertEqual(report["summary"]["harness_source_part_count"], 15)'
new = 'self.assertEqual(report["summary"]["harness_source_part_count"], 17)'
if old not in test_text and new not in test_text:
    raise SystemExit("could not find harness source part count assertion")
test_text = test_text.replace(old, new, 1)
test_path.write_text(test_text, encoding="utf-8")

print("updated profiles:", ", ".join(updated_profiles))
'@
    Invoke-PythonBlock 'Update required profiles and parity test count' $updateCode

    Invoke-Checked 'Build PowerShell surface inventory reports' {
        python project_sources/collector/tools/build_powershell_surface_inventory.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_surface_inventory.json `
            --markdown-output project_sources/collector/powershell_surface_inventory.md
    }
    Invoke-Checked 'Build PowerShell assembly parity reports' {
        python project_sources/collector/tools/run_powershell_assembly_parity.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_assembly_parity_report.json `
            --markdown-output project_sources/collector/powershell_assembly_parity_report.md
    }
    Invoke-Checked 'Build PowerShell review assist reports' {
        python project_sources/collector/tools/run_powershell_review_assist_report.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_review_assist_report.json `
            --markdown-output project_sources/collector/powershell_review_assist_report.md
    }

    $assertCode = @'
from pathlib import Path
import json
import re

repo = Path(".").resolve()

def load_json(rel_path: str) -> dict:
    return json.loads((repo / rel_path).read_text(encoding="utf-8"))

expected_harness_paths = [
    f"project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-{index:03d}.ps1.txt"
    for index in range(17)
]

profiles = load_json(".github/github_actions/workflow_required_surface_profiles.json")
for name, value in profiles.items():
    if not isinstance(value, list):
        continue
    harness_paths = [
        item for item in value
        if item.startswith("project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-")
    ]
    if not harness_paths:
        continue
    suffixes = [re.search(r"part-(\d{3})", path).group(1) for path in harness_paths]
    expected_suffixes = [f"{index:03d}" for index in range(17)]
    if suffixes != expected_suffixes:
        raise SystemExit(f"{name} harness profile is not contiguous 000..016: {suffixes}")

inventory = load_json("project_sources/collector/powershell_surface_inventory.json")
if not inventory["validation"]["success"]:
    raise SystemExit(f"surface inventory validation failed: {inventory['validation']['errors']}")
inventory_summary = inventory["summary"]
if inventory_summary["total_surfaces"] != 250:
    raise SystemExit(f"expected 250 total surfaces, found {inventory_summary['total_surfaces']}")
if inventory_summary["by_category"]["collector_harness_source_part"] != 17:
    raise SystemExit("surface inventory harness category count is not 17")
if inventory_summary["by_source_type"][".ps1.txt"] != 17:
    raise SystemExit("surface inventory .ps1.txt count is not 17")
if inventory_summary["by_status"]["source_part"] != 17:
    raise SystemExit("surface inventory source_part count is not 17")
if inventory_summary["by_inclusion_decision"]["include"] != 121:
    raise SystemExit("surface inventory include count is not 121")
controls = inventory["controls"]["harness_source_parts"]
if controls["part_count"] != 17:
    raise SystemExit("harness control part_count is not 17")
if controls["required_profile_part_count"] != 17:
    raise SystemExit("harness required profile part count is not 17")
if controls["required_profile_present_count"] != 17:
    raise SystemExit("harness required profile present count is not 17")
if [entry["path"] for entry in controls["parts"]] != expected_harness_paths:
    raise SystemExit("surface inventory harness control paths are not exactly 000..016")

parity = load_json("project_sources/collector/powershell_assembly_parity_report.json")
if not parity["validation"]["success"]:
    raise SystemExit(f"assembly parity validation failed: {parity['validation']['errors']}")
parity_summary = parity["summary"]
expected_parity_summary = {
    "collector_source_part_count": 38,
    "harness_source_part_count": 17,
    "source_part_count": 55,
    "source_input_count": 56,
    "generated_output_count": 2,
    "parse_status": "pass",
    "parity_status": "pass",
}
for key, expected in expected_parity_summary.items():
    actual = parity_summary[key]
    if actual != expected:
        raise SystemExit(f"assembly parity summary {key} expected {expected!r}, found {actual!r}")
if [entry["path"] for entry in parity["source_maps"]["harness"]] != expected_harness_paths:
    raise SystemExit("assembly parity harness source maps are not exactly 000..016")
outputs = {entry["id"]: entry for entry in parity["generated_outputs"]}
harness_output = outputs["harness_generated_tests"]
if harness_output["source_input_count"] != 17:
    raise SystemExit("harness generated output source input count is not 17")
if harness_output["line_count"] != 2943:
    raise SystemExit(f"unexpected harness generated line count {harness_output['line_count']}")
if harness_output["sha256"] != "61914542813822c2fd38efb0c4ecada94160c8928dc10fb6707a622798379fe5":
    raise SystemExit("harness generated output sha256 changed")
if [entry["source_path"] for entry in harness_output["line_mapping"]] != expected_harness_paths:
    raise SystemExit("harness generated line mapping is not exactly 000..016")

review = load_json("project_sources/collector/powershell_review_assist_report.json")
if not review["validation"]["success"]:
    raise SystemExit(f"review assist validation failed: {review['validation']['errors']}")
review_parity = review["evidence_channels"]["assembly_parity"]["summary"]
for key in ("harness_source_part_count", "source_part_count", "source_input_count"):
    if review_parity[key] != parity_summary[key]:
        raise SystemExit(f"review assist parity summary {key} expected {parity_summary[key]}, found {review_parity[key]}")
review_inventory = review["surface_inventory"]["summary"]
if review_inventory["total_surfaces"] != 250:
    raise SystemExit("review assist embedded inventory total surfaces is not 250")
if review_inventory["by_category"]["collector_harness_source_part"] != 17:
    raise SystemExit("review assist embedded inventory harness category count is not 17")
if review_inventory["by_source_type"][".ps1.txt"] != 17:
    raise SystemExit("review assist embedded inventory .ps1.txt count is not 17")
if review_inventory["by_status"]["source_part"] != 17:
    raise SystemExit("review assist embedded inventory source_part count is not 17")
if review_inventory["by_inclusion_decision"]["include"] != 121:
    raise SystemExit("review assist embedded inventory include count is not 121")

print("evidence assertions passed")
'@
    Invoke-PythonBlock 'Assert refreshed harness evidence counts and maps' $assertCode

    Invoke-Checked 'Surface inventory no-write validation' {
        python project_sources/collector/tools/build_powershell_surface_inventory.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_surface_inventory.json `
            --markdown-output project_sources/collector/powershell_surface_inventory.md `
            --no-write
    }
    Invoke-Checked 'Assembly parity no-write validation' {
        python project_sources/collector/tools/run_powershell_assembly_parity.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_assembly_parity_report.json `
            --markdown-output project_sources/collector/powershell_assembly_parity_report.md `
            --no-write
    }
    Invoke-Checked 'Review assist no-write validation' {
        python project_sources/collector/tools/run_powershell_review_assist_report.py `
            --repo-root . `
            --json-output project_sources/collector/powershell_review_assist_report.json `
            --markdown-output project_sources/collector/powershell_review_assist_report.md `
            --no-write
    }
    Invoke-Checked 'Assembly parity unit tests' {
        python project_sources/collector/tools/test_run_powershell_assembly_parity.py
    }

    $expectedChanged = @(
        '.github/github_actions/workflow_required_surface_profiles.json',
        'project_sources/collector/tools/powershell_assembly_parity_test_real_repo.py',
        'project_sources/collector/powershell_surface_inventory.json',
        'project_sources/collector/powershell_surface_inventory.md',
        'project_sources/collector/powershell_assembly_parity_report.json',
        'project_sources/collector/powershell_assembly_parity_report.md',
        'project_sources/collector/powershell_review_assist_report.json',
        'project_sources/collector/powershell_review_assist_report.md'
    )
    $changed = @(git status --short | ForEach-Object { $_.Substring(3) })
    $unexpected = @($changed | Where-Object { $expectedChanged -notcontains $_ })
    if ($unexpected.Count -gt 0) {
        throw "Unexpected changed files: $($unexpected -join ', ')"
    }
    $missing = @($expectedChanged | Where-Object { $changed -notcontains $_ })
    if ($missing.Count -gt 0) {
        throw "Expected evidence changes missing: $($missing -join ', ')"
    }

    Invoke-Checked 'Stage refreshed evidence files' { git add -- $expectedChanged }
    Invoke-Checked 'Commit refreshed evidence' { git commit -m 'Refresh harness part 004 split evidence' }
    $NewHead = (git rev-parse HEAD).Trim()
    Invoke-Checked 'Push refreshed evidence to PR branch' { git push origin "HEAD`:refs/heads/$TargetBranch" }

    $summaryData = [ordered]@{
        schema = 'dcoir.chatgpt_staging.exec_summary.v1'
        request_id = $RequestId
        target_branch = $TargetBranch
        expected_input_head = $ExpectedHead
        pushed_head = $NewHead
        changed_files = $expectedChanged
        assertions = [ordered]@{
            harness_parts = '000..016'
            surface_inventory_total_surfaces = 250
            surface_inventory_harness_source_parts = 17
            assembly_parity_collector_source_parts = 38
            assembly_parity_harness_source_parts = 17
            assembly_parity_source_parts = 55
            assembly_parity_source_inputs = 56
            harness_generated_tests_sha256 = '61914542813822c2fd38efb0c4ecada94160c8928dc10fb6707a622798379fe5'
            parse_status = 'pass'
            parity_status = 'pass'
        }
        validation = @(
            'build_powershell_surface_inventory.py --no-write',
            'run_powershell_assembly_parity.py --no-write',
            'run_powershell_review_assist_report.py --no-write',
            'test_run_powershell_assembly_parity.py'
        )
        created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
}
finally {
    if ($switchedToTarget) {
        $dirtyFiles = @(git status --porcelain)
        if ($dirtyFiles.Count -gt 0) {
            Invoke-Checked 'Stash target branch working tree before status return' { git stash push --include-untracked -m "$RequestId return-to-main cleanup" }
        }
        Invoke-Checked 'Return checkout to main for exec status commit' { git fetch --no-tags origin "refs/heads/$MainBranch`:refs/remotes/origin/$MainBranch" }
        Invoke-Checked 'Checkout main for exec status commit' { git checkout -B chatgpt-exec-request-source "origin/$MainBranch" }
    }
}

if ($null -ne $summaryData) {
    $summaryDir = Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $RequestId
    New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
    $summaryPath = Join-Path $summaryDir 'harness_part004_evidence_refresh_summary.json'
    $summaryData | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryPath -Encoding utf8
    Write-Host "Wrote tracked summary $summaryPath"
}
