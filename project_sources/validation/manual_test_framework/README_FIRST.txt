DCOIR Manual Test Framework Bundle v9

What changed in v9
- The framework has a deterministic bundle builder: build_dcoir_manual_test_framework_bundle.py.
- The install helper accepts -BundlePath and otherwise uses the newest dcoir_manual_test_framework_bundle_*_full.zip in Downloads.
- The installer no longer depends on an old hard-coded v8 download filename.
- The Git and Python prerequisite rows are bound to bootstrap results instead of staying stuck at PENDING.
- The staged collector runtime lives under _test_output\live_runtime instead of cluttering the root folder.
- The admin phase launches through the PowerShell launcher so the elevated window follows the same dashboard path.
- The framework removes staged runtime files and transient build/staging folders during cleanup.
- Expected non-admin collector limitations are graded as PASS with honest notes instead of surfacing as framework PARTIAL results.
- Quick help is expected to print and return cleanly without relying on the old nonzero-exit quirk.
- Contextual help is part of the graded manual test surface.
- Review-surface tuning checks are part of the graded manual test surface.
- The framework records a bounded T2-pathway mapping follow-on note so the operator does not lose that required live proof step.

Files
- run_dcoir_manual_tests.ps1 : bootstrap launcher
- dcoir_manual_test_runner.py : terminal dashboard and test engine
- dcoir_manual_runner_context.py : shared state, dashboard, path, and command helpers
- dcoir_manual_runner_package.py : repository, package, and runtime staging helpers
- dcoir_manual_runner_checks.py and dcoir_manual_runner_checks_part_*.py : manual collector test steps and result checks
- dcoir_manual_runner_flow.py : top-level non-admin/admin orchestration flow
- dcoir_manual_test_control.json : durable control surface for step/order/cleanup naming
- DCOIR_manual_test_plan.md : ordered manual test plan
- README_FIRST.txt : this file
- install_and_run_from_downloads.ps1 : optional one-shot installer/runner helper
- build_dcoir_manual_test_framework_bundle.py : deterministic ZIP builder for the downloadable bundle

Build the downloadable bundle from a repo checkout
From the repository root:

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "python .\project_sources\validation\manual_test_framework\build_dcoir_manual_test_framework_bundle.py --source-dir .\project_sources\validation\manual_test_framework --output-dir .\project_sources\validation\manual_test_framework\out_manual_test_framework_bundle --version v9"

The default ZIP name is:

dcoir_manual_test_framework_bundle_v9_full.zip

Install and run from a downloaded bundle
Option A: Put the newest dcoir_manual_test_framework_bundle_*_full.zip in Downloads, then run:

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_and_run_from_downloads.ps1

Option B: Provide the exact bundle path:

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_and_run_from_downloads.ps1 -BundlePath "C:\Users\<you>\Downloads\dcoir_manual_test_framework_bundle_v9_full.zip"

Run after manual extraction
1. Put all files from this bundle in one folder, for example C:\DCOIR_TESTER.
2. Open a normal PowerShell window.
3. Run:

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_dcoir_manual_tests.ps1

What the launcher does
- Checks Git and Python.
- Tries to install missing prerequisites with winget.
- Refreshes the current PATH.
- Launches the dashboard.

What the dashboard does
- Shows every test on load.
- Updates STATUS live as each test starts and finishes.
- Shows only high-level status and next-action text in the terminal.
- Writes all command output, errors, and detailed traces into:
  .\_test_output\DCOIR_Collector_Full_Signoff_Report.txt

Important notes
- The framework stages runtime files inside _test_output\live_runtime.
- The framework intentionally preserves the report/state/runs for review after the run.
- Richer contextual help is part of the current testable collector surface.
- Review-surface tuning and the bounded T2-pathway follow-on are part of the current testable collector surface.
- Source/readback validation can prove this bundle lane is wired correctly, but final runtime confidence still requires running the launcher on a Windows workstation with PowerShell 5.1 available.
