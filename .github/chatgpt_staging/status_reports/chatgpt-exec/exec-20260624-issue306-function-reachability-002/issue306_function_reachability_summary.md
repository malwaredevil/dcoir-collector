# Issue #306 function reachability staging summary

- request_id: exec-20260624-issue306-function-reachability-002
- result: success
- target_branch: codex/issue-306-function-reachability-report
- expected_start_head: a04a447be79d1fe44e77f2e6c98222622a4680d6
- new_head: b55f03b8926264da08cc5790917699fce4469507
- pushed_head: b55f03b8926264da08cc5790917699fce4469507

## Changed paths

- .github/actions/run-powershell-review-assist/action.yml
- project_sources/collector/powershell_function_reachability_report.json
- project_sources/collector/powershell_function_reachability_report.md
- project_sources/collector/powershell_review_assist_report.json
- project_sources/collector/powershell_review_assist_report.md
- project_sources/collector/tools/run_powershell_function_reachability_report.py
- project_sources/collector/tools/run_powershell_review_assist_report.py
- project_sources/collector/tools/test_run_powershell_function_reachability_report.py
- project_sources/collector/tools/test_run_powershell_review_assist_report.py

## Validation

- python -m py_compile touched report scripts/tests: passed
- function reachability no-write validation: passed
- review-assist no-write validation: passed
- 8 function reachability tests: passed
- 21 review-assist tests: passed
- 225 PowerShell report unittest discovery tests: passed
- git diff --check: passed
