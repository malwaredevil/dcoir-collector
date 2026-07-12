

def assert_problem(summary: str) -> None:
    try:
        mod.normalize_findings({"summary": summary, "findings": []}, config, line_index)
    except mod.ReviewQualityError as exc:
        assert "summary indicated a possible issue" in str(exc)
    else:
        raise AssertionError(f"summary should fail review quality: {summary}")


for clean_summary in [
    "No high-confidence inline findings were found.",
    "No high-confidence issues.",
    "No actionable issues remain.",
    "No high-confidence regressions.",
    "No issues, regressions, or risks were identified.",
    "No findings, issues, regressions, or failures remain.",
    "No security issues, workflow regressions, or operational risks remain.",
    "No security issues, workflow regressions or operational risks remain.",
    "No security issues and workflow regressions remain.",
    "No security issues and regressions remain.",
    "No findings and issues were identified.",
    "No findings.",
    "No workflow security risks were identified.",
    "No regressions found.",
    "No regressions found and no security risks remain.",
    "No regressions found. No security risks remain.",
    "No high-confidence actionable findings. The PR hardens native GitHub suggestion verification by anchoring replacements to the actual file text, reducing the maximum length, blocking multi-line and marker-containing suggestions, and rejecting suggestions when the changed-line count is not exactly one. Both the verifier and the selftest new coverage look correct. The changed code does not introduce any correctness, security, governance, Windows PowerShell 5.1 compatibility, or validation-gap risk.",
]:
    assert_clean(clean_summary)

for problem_summary in [
    "The only high-signal finding is a governance regression.",
    "No high-confidence inline findings were found, but the only high-signal finding is a governance regression.",
    "No findings and security risks remain.",
    "No issues and security risks remain.",
    "No workflow security risks were identified, but validation should reject unanchored findings.",
    "No regressions found, but security risks remain.",
    "No regressions found and security risks remain.",
    "No findings and this security risk remains.",
    "No findings and the workflow regression remains.",
    "No regressions found. Security risks remain.",
    "No regressions found, security risks remain.",
    "The changed code does not introduce compatibility problems. Security risks remain.",
    "No issues, regressions, or risks were identified, security risks remain.",
    "No issues, security risks remain.",
    "No issues, regressions, security risks remain.",
    "No security issues, workflow regressions, operational risks remain.",
]:
    assert_problem(problem_summary)


multiline_subprocess_diff = """diff --git a/tools/run_probe.py b/tools/run_probe.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/run_probe.py
@@ -0,0 +1,6 @@
+import subprocess
+def run_probe(command):
+    subprocess.run(
+        command,
+        shell=True,
+    )
+"""
multiline_sentinels = mod.detect_risk_sentinels(multiline_subprocess_diff)
assert any(
    item.path == "tools/run_probe.py"
    and item.line == 5
    and item.label == "shell=True subprocess invocation"
    for item in multiline_sentinels
)
assert len({(item.path, item.line, item.label) for item in multiline_sentinels}) == len(multiline_sentinels)

comment_only_diff = """diff --git a/tools/comment_examples.py b/tools/comment_examples.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/comment_examples.py
@@ -0,0 +1,4 @@
+# avoid subprocess.run("echo hi", shell=True) in production
+# Invoke-Expression is intentionally mentioned in this comment-only example
+# Remove-Item -Recurse also appears only as documentation
+
+"""
assert mod.detect_risk_sentinels(comment_only_diff) == []

probe_diff = """diff --git a/validation-review-probes/Invoke-IntentionalFlawedReviewBaseline.ps1 b/validation-review-probes/Invoke-IntentionalFlawedReviewBaseline.ps1
index 0000000..1111111 100644
--- /dev/null
+++ b/validation-review-probes/Invoke-IntentionalFlawedReviewBaseline.ps1
@@ -0,0 +1,61 @@
+function New-OsqueryStatement {
+    param([string]$Filter)
+    return "SELECT pid, name, path FROM processes WHERE name LIKE '%$Filter%';"
+}
+function Invoke-CollectorProbe {
+    param([string]$Path, [string]$CommandText)
+    Invoke-Expression "Get-ChildItem $Path | Where-Object Name -like '$CommandText'"
+}
+function Test-ShouldEscalate {
+    if ($Severity -eq "High" -or "Critical") {
+        return $true
+    }
+}
+function Remove-ProbeWorkspace {
+    Remove-Item $Path -Recurse -Force
+}
+function Write-RequestedFile {
+    param([pscustomobject]$Request)
+    $targetPath = Join-Path -Path (Get-Location).Path -ChildPath $Request.RelativePath
+    Set-Content -Path $targetPath -Value $Request.Content -Encoding utf8
+}
+function Send-CaseContext {
+    $payload = @{ env = Get-ChildItem Env: | ForEach-Object { "$($_.Name)=$($_.Value)" } }
+}
diff --git a/validation-review-probes/intentional_flawed_review_baseline.py b/validation-review-probes/intentional_flawed_review_baseline.py
index 0000000..2222222 100644
--- /dev/null
+++ b/validation-review-probes/intentional_flawed_review_baseline.py
@@ -0,0 +1,52 @@
+def build_process_query(hostname, operator_filter):
+    return f"WHERE hostname = '{hostname}' AND name LIKE '%{operator_filter}%';"
+def write_triage_note(case_id, note, output_dir):
+    subprocess.run(f"git add {destination}", shell=True, check=False)
+def should_escalate(severity, confidence):
+    if severity == "critical" or "high":
+        return True
+def cleanup_collector_workspace(path_from_comment):
+    shutil.rmtree(path_from_comment, ignore_errors=True)
+def export_env_to_report(report_path):
+    Path(report_path).write_text("\\n".join(f"{key}={value}" for key, value in os.environ.items()))
"""
sentinels = mod.detect_risk_sentinels(probe_diff)
assert len(sentinels) >= 10
assert any(item.path.endswith(".py") and item.label == "shell=True subprocess invocation" for item in sentinels)
assert any(item.path.endswith(".py") and item.label == "truthy literal branch condition" for item in sentinels)
assert any(item.path.endswith(".ps1") and item.label == "PowerShell Invoke-Expression" for item in sentinels)
assert any(item.path.endswith(".ps1") and item.label == "PowerShell unsafe file-write path" for item in sentinels)
assert any(item.path.endswith(".ps1") and item.label == "environment dump or exfiltration primitive" for item in sentinels)
assert mod.detect_risk_sentinels(
    """diff --git a/docs/examples.md b/docs/examples.md
index 0000000..1111111 100644
--- /dev/null
+++ b/docs/examples.md
@@ -0,0 +1,2 @@
+Example text mentions subprocess.run("echo hi", shell=True) for reviewer education.
""",
) == []

risk_prompt = mod.build_prompt(
    {"number": 287, "title": "Validation probe", "body": "Disposable validation baseline."},
    [
        {"filename": "validation-review-probes/intentional_flawed_review_baseline.py", "status": "added"},
        {"filename": "validation-review-probes/Invoke-IntentionalFlawedReviewBaseline.ps1", "status": "added"},
    ],
    probe_diff,
    config,
    sentinels,
)
assert "Changed-code risk signals detected before model review" in risk_prompt
assert "command/process execution" in risk_prompt
assert "container/orchestration privilege escalation" in risk_prompt
assert "Project emphasis" in risk_prompt
assert "PowerShell collectors" in risk_prompt
assert "GitHub Actions/YAML" in risk_prompt
assert "shell=True subprocess invocation" in risk_prompt
assert "PowerShell Invoke-Expression" in risk_prompt
assert "PowerShell unsafe file-write path" in risk_prompt
