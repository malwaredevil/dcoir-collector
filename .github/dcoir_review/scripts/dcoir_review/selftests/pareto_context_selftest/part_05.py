class FakeErrorBody:
    def read(self) -> bytes:
        return json.dumps({"error": {"message": "No endpoints found that can handle the requested parameters."}}).encode("utf-8")

    def close(self) -> None:
        return None


called_models: list[str] = []
original_request_once = mod.hardened.openrouter_request_once
empty_headers = Message()


def fake_request_once(_prompt: str, _schema: dict, _config: object, _ignored: list[str], model: str):
    called_models.append(model)
    if model == "openrouter/pareto-code":
        raise urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=404,
            msg="No endpoints found",
            hdrs=empty_headers,
            fp=FakeErrorBody(),
        )
    return {"summary": "No findings.", "findings": []}, "fallback-model", ""


mod.hardened.openrouter_request_once = fake_request_once
try:
    result, model_used, _tier = mod.hardened.openrouter_review("prompt", schema, config, None)
finally:
    mod.hardened.openrouter_request_once = original_request_once
assert called_models == ["openrouter/pareto-code", "openrouter/auto"]
assert model_used == "fallback-model"
assert result["findings"] == []

unsafe_context_summary = "included hostile/@codex.py and @malwaredevil-owned/file.py"
safe_context_summary = mod.sanitize_context_summary(unsafe_context_summary, config)
assert "@codex" not in safe_context_summary
assert "@malwaredevil" not in safe_context_summary
assert "@<!-- -->codex" in safe_context_summary

review_body = mod.append_context_to_review_body(mod.base.MARKER, "first-pass-deep", deep_summary, config)
assert "Context mode: `first-pass-deep`" in review_body
assert "Context readback:" in review_body
unsafe_review_body = mod.append_context_to_review_body(
    mod.base.MARKER,
    "first-pass-deep",
    unsafe_context_summary,
    config,
)
assert "@codex" not in unsafe_review_body
assert "@malwaredevil" not in unsafe_review_body
assert "@<!-- -->codex" in unsafe_review_body


off_diff_fallback_result = {
    "summary": "Review found an off-diff issue.",
    "findings": [
        {
            "path": "unrelated/off_diff.py",
            "line": 12,
            "severity": "high",
            "confidence": 0.99,
            "title": "Off-diff finding",
            "body": "This finding is not in a changed file for this PR.",
        }
    ],
}
try:
    mod.split_findings_with_review_body_fallback(
        off_diff_fallback_result,
        config,
        {(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py", 1216): 1},
    )
except mod.hardened.ReviewQualityError as exc:
    assert "not in changed diff" in str(exc)
else:
    raise AssertionError("off-diff fallback finding should preserve the review quality failure")

changed_file_unanchored_result = {
    "summary": "Review found a changed-file issue outside added lines.",
    "findings": [
        {
            "path": ".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py",
            "line": 1220,
            "severity": "high",
            "confidence": 0.99,
            "title": "Changed-file unanchored finding",
            "body": "This finding is in a changed file but not on an added line.",
        }
    ],
}
inline_findings, review_body_findings = mod.split_findings_with_review_body_fallback(
    changed_file_unanchored_result,
    config,
    {(".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py", 1216): 1},
)
assert inline_findings == []
assert len(review_body_findings) == 1
assert review_body_findings[0]["path"] == ".github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py"
assert "not an added changed line" in review_body_findings[0]["_unanchored_reason"]


ranking_budget_config = mod.copy.copy(config)
ranking_budget_config.max_inline_comments = 5
ranking_budget_config.required_finding_reserved_budget = 5
ranking_budget_config.required_finding_min_per_family = 1
ranking_budget_findings = [
    {
        "path": "web/app.ts",
        "line": 10,
        "severity": "high",
        "confidence": 0.99,
        "title": "Optional TypeScript finding",
        "body": "Optional TypeScript issue should not crowd out required operational families.",
    },
    {
        "path": "k8s/deployment.yaml",
        "line": 11,
        "severity": "high",
        "confidence": 0.99,
        "title": "Optional Kubernetes finding",
        "body": "Optional Kubernetes issue should stay behind required operational families when budget is tight.",
    },
    {
        "path": "scripts/ops.ps1",
        "line": 12,
        "severity": "medium",
        "confidence": 0.96,
        "title": "PowerShell finding",
        "body": "PowerShell operational risk must keep a reserved slot.",
    },
    {
        "path": "scripts/check.py",
        "line": 13,
        "severity": "medium",
        "confidence": 0.96,
        "title": "Python finding",
        "body": "Python operational risk must keep a reserved slot.",
    },
    {
        "path": ".github/workflows/ci.yml",
        "line": 14,
        "severity": "medium",
        "confidence": 0.96,
        "title": "GitHub Actions finding",
        "body": "GitHub Actions workflow risk must keep a reserved slot.",
    },
    {
        "path": "web/extra.ts",
        "line": 15,
        "severity": "medium",
        "confidence": 0.95,
        "title": "Second TypeScript finding",
        "body": "Extra optional issue competes only after required families are represented.",
    },
]
ranked_required_budget_findings = mod.rank_findings_for_required_budget(ranking_budget_findings, ranking_budget_config)
ranked_required_families = [mod.finding_review_family(item) for item in ranked_required_budget_findings]
assert len(ranked_required_budget_findings) == 5
assert "powershell" in ranked_required_families
assert "python" in ranked_required_families
assert "github-actions-yaml" in ranked_required_families
assert ranked_required_families.index("powershell") < 5
assert ranked_required_families.index("python") < 5
assert ranked_required_families.index("github-actions-yaml") < 5

original_detector_findings = [
    {
        "path": "scripts/ops.ps1",
        "line": 42,
        "severity": "high",
        "confidence": 0.79,
        "title": "Detector-proposed fix",
        "body": "Detector pass should not be trusted to provide a native GitHub suggestion.",
        "suggested_replacement": "Write-Output 'fixed'",
    }
]
stripped_detector_findings = mod.strip_detector_suggested_replacements(original_detector_findings)
assert original_detector_findings[0]["suggested_replacement"] == "Write-Output 'fixed'"
assert stripped_detector_findings[0]["suggested_replacement"] == ""
assert stripped_detector_findings[0]["_detector_suggested_replacement"] == "Write-Output 'fixed'"

print("Pareto context DCOIR Review selftest passed")
