diverse_risk_diff = """diff --git a/probes/kubernetes.yml b/probes/kubernetes.yml
index 0000000..1111111 100644
--- /dev/null
+++ b/probes/kubernetes.yml
@@ -0,0 +1,14 @@
+apiVersion: v1
+kind: Pod
+spec:
+  hostNetwork: true
+  containers:
+    - securityContext:
+        privileged: true
+        allowPrivilegeEscalation: true
+        runAsUser: 0
+  volumes:
+    - name: host-root
+      hostPath:
+        path: /
diff --git a/probes/operator.ps1 b/probes/operator.ps1
index 0000000..2222222 100644
--- /dev/null
+++ b/probes/operator.ps1
@@ -0,0 +1,8 @@
+Expand-Archive -Path $Request.Archive -DestinationPath $Request.ExtractTo -Force
+Start-Process -FilePath $Request.Tool -ArgumentList $Request.Arguments -Wait
+Invoke-WebRequest -Uri $Request.CallbackUrl -Headers @{ Authorization = "Bearer $($Request.Token)" } -OutFile (Join-Path $env:TEMP $Request.OutputName)
+$acl = Get-Acl -LiteralPath $Request.TargetPath
+$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")
+$acl.SetAccessRule($rule)
+Set-Acl -LiteralPath $Request.TargetPath -AclObject $acl
diff --git a/probes/pipeline.ts b/probes/pipeline.ts
index 0000000..3333333 100644
--- /dev/null
+++ b/probes/pipeline.ts
@@ -0,0 +1,12 @@
+const destination = path.join(workspace, request.destination);
+writeFileSync(destination, request.body, "utf8");
+exec(`powershell -NoProfile ${request.command}`);
+const mapper = new Function("record", request.expression);
+const query = `select * from alerts where owner = '${request.userId}' and ${request.sqlFilter}`;
+await fetch(request.url, { headers: { Authorization: process.env.PROVIDER_TOKEN } });
diff --git a/probes/workflow.yml b/probes/workflow.yml
index 0000000..4444444 100644
--- /dev/null
+++ b/probes/workflow.yml
@@ -0,0 +1,10 @@
+on:
+  pull_request_target:
+jobs:
+  unsafe:
+    steps:
+      - uses: actions/checkout@v7
+        with:
+          ref: ${{ github.event.pull_request.head.ref }}
+      - run: bash -c "${{ github.event.pull_request.title }}"
+      - run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"
"""
diverse_sentinels = mod.detect_risk_sentinels(diverse_risk_diff, 12)
diverse_labels = {item.label for item in diverse_sentinels}
assert "TypeScript/JavaScript unsafe path construction" in diverse_labels
assert "TypeScript/JavaScript unsafe file write" in diverse_labels
assert "Node.js command execution" in diverse_labels
assert "PowerShell process launch" in diverse_labels
assert "PowerShell unsafe archive extraction" in diverse_labels
assert "PowerShell outbound request or download" in diverse_labels
assert "CI token exfiltration primitive" in diverse_labels
assert "GitHub Actions privileged PR context" in diverse_labels
assert "Kubernetes privileged container setting" in diverse_labels
assert "Kubernetes host filesystem exposure" in diverse_labels
assert len({item.path for item in diverse_sentinels}) >= 4
required_diverse_labels = {item.label for item in mod.required_risk_sentinels(diverse_sentinels)}
assert "PowerShell process launch" in required_diverse_labels
assert "PowerShell unsafe archive extraction" in required_diverse_labels
assert "PowerShell outbound request or download" in required_diverse_labels
assert "GitHub Actions privileged PR context" in required_diverse_labels
assert "CI token exfiltration primitive" in required_diverse_labels
assert "Node.js command execution" not in required_diverse_labels
assert "TypeScript/JavaScript unsafe path construction" not in required_diverse_labels
assert "Kubernetes privileged container setting" not in required_diverse_labels

calls: list[str] = []
original_openrouter_review = mod.openrouter_review


def fake_openrouter_review(prompt: str, _schema: dict, _config: object, _reporter: object | None = None):
    calls.append(prompt)
    if len(calls) == 1:
        return {"summary": "No high-confidence inline findings were found.", "findings": []}, "weak-model", ""
    return {
        "summary": "Found unsafe shell execution.",
        "findings": [
            {
                "title": "Avoid shell execution",
                "severity": "high",
                "confidence": 0.95,
                "path": "validation-review-probes/intentional_flawed_review_baseline.py",
                "line": 4,
                "body": "shell=True executes constructed text.",
                "suggested_replacement": "",
                "validation": "python3 .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py",
            }
        ],
    }, "strong-model", ""


mod.openrouter_review = fake_openrouter_review
try:
    retry_result, retry_model, _retry_tier = mod.openrouter_review_with_quality_retry(
        "initial prompt",
        schema,
        config,
        None,
        sentinels,
    )
finally:
    mod.openrouter_review = original_openrouter_review
assert len(calls) == 2
assert retry_model == "strong-model"
assert retry_result["findings"]
assert "Review quality retry" in calls[1]
assert "validation-review-probes/intentional_flawed_review_baseline.py" in calls[1]

tiny_retry_config = copy.copy(config)
tiny_retry_config.max_prompt_chars = 240
tiny_retry_prompt = mod.build_quality_retry_prompt("x" * 1000, {"summary": "No findings."}, sentinels, tiny_retry_config)
assert len(tiny_retry_prompt) <= tiny_retry_config.max_prompt_chars

try:
    mod.enforce_risk_sentinel_findings([], sentinels, config)
except mod.ReviewQualityError as exc:
    assert "high-risk changed-line signals" in str(exc)
else:
    raise AssertionError("empty findings after risk-sentinel retry should fail review quality")

try:
    mod.enforce_risk_sentinel_findings(
        [
            {
                "title": "Unrelated accepted finding",
                "severity": "high",
                "confidence": 0.95,
                "path": sentinels[0].path,
                "line": sentinels[0].line,
                "body": "This finding is actionable but does not mention the sentinel risk class.",
                "suggested_replacement": "",
                "validation": "python3 .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py",
            }
        ],
        sentinels,
        config,
    )
except mod.ReviewQualityError as exc:
    assert "did not produce actionable findings covering those signals" in str(exc)
else:
    raise AssertionError("unrelated findings must not satisfy risk-sentinel coverage")

fallback_findings = mod.add_risk_sentinel_fallback_findings([], sentinels, config)
assert fallback_findings
assert all(finding["title"].startswith("Deterministic risk sentinel:") for finding in fallback_findings)
mod.enforce_risk_sentinel_findings(fallback_findings, sentinels, config)
mod.enforce_risk_sentinel_findings([], [], config)
optional_only_sentinels = [
    item
    for item in diverse_sentinels
    if item.label in {"Node.js command execution", "TypeScript/JavaScript unsafe path construction", "Kubernetes host filesystem exposure"}
]
assert optional_only_sentinels
assert mod.required_risk_sentinels(optional_only_sentinels) == []
assert mod.add_risk_sentinel_fallback_findings([], optional_only_sentinels, config) == []
mod.enforce_risk_sentinel_findings([], optional_only_sentinels, config)

full_budget_config = copy.copy(config)
full_budget_config.max_inline_comments = 2
covered_sentinel, uncovered_sentinel = sentinels[0], sentinels[1]
full_budget_findings = [
    {
        "title": f"Covered deterministic risk: {covered_sentinel.label}",
        "severity": "critical",
        "confidence": 0.99,
        "path": covered_sentinel.path,
        "line": covered_sentinel.line,
        "body": f"{covered_sentinel.detail}. {covered_sentinel.label}.",
        "suggested_replacement": "",
        "validation": "python3 .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py",
    },
    {
        "title": "Lower-priority model finding",
        "severity": "low",
        "confidence": 0.70,
        "path": covered_sentinel.path,
        "line": covered_sentinel.line,
        "body": "Useful but lower-priority context that does not cover the uncovered sentinel.",
        "suggested_replacement": "",
        "validation": "python3 .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py",
    },
]
augmented_full_budget = mod.add_risk_sentinel_fallback_findings(
    full_budget_findings,
    [covered_sentinel, uncovered_sentinel],
    full_budget_config,
)
assert len(augmented_full_budget) == 2
assert any(finding["title"] == f"Covered deterministic risk: {covered_sentinel.label}" for finding in augmented_full_budget)
assert any(
    finding["title"] == f"Deterministic risk sentinel: {uncovered_sentinel.label}" for finding in augmented_full_budget
)
assert not any(finding["title"] == "Lower-priority model finding" for finding in augmented_full_budget)
mod.enforce_risk_sentinel_findings(
    augmented_full_budget,
    [covered_sentinel, uncovered_sentinel],
    full_budget_config,
)

print("hardened DCOIR Review selftest passed")
