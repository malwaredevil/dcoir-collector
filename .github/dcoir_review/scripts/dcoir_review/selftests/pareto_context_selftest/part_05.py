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

class FakeHybridReporter:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str]] = []

    def update(self, stage: str, detail: str) -> None:
        self.updates.append((stage, detail))


hybrid_diff = """diff --git a/docs/review.md b/docs/review.md
index 1111111..2222222 100644
--- a/docs/review.md
+++ b/docs/review.md
@@ -1,2 +1,3 @@
 Review gates remain required.
+External review may be skipped after local checks.
 Keep issue receipts current.
"""
hybrid_line_index = mod.hardened.build_added_line_index(hybrid_diff)
assert ("docs/review.md", 2) in hybrid_line_index

hybrid_config = mod.copy.copy(config)
hybrid_config.per_file_first_pass_review = True
hybrid_config.per_file_review_concurrency = 1
hybrid_reporter = FakeHybridReporter()
original_build_file_contexts = mod.build_file_contexts
original_review_single_file_context = mod.review_single_file_context
original_build_prompt = mod.build_prompt
original_hybrid_openrouter_review = mod.hardened.openrouter_review


def fake_build_file_contexts(_gh: object, _pr: dict, _files: list[dict], _config: object) -> list[dict]:
    return [{"path": "docs/review.md", "item": {"filename": "docs/review.md"}, "text": "review"}]


def fake_review_single_file_context(*_args: object, **_kwargs: object) -> dict:
    return {
        "path": "docs/review.md",
        "prompt_chars": 120,
        "result": {
            "summary": "A possible review-gate issue remains, but no actionable changed-line finding was identified.",
            "findings": [],
        },
        "model_used": "detector-model",
        "service_tier": "",
    }


def fake_hybrid_repair_review(
    _prompt: str,
    _schema: dict,
    _config: object,
    _reporter: object | None = None,
) -> tuple[dict, str, str]:
    return (
        {
            "summary": "A possible review-gate issue remains, but no actionable changed-line finding was identified.",
            "findings": [],
        },
        "repair-model",
        "",
    )


mod.build_file_contexts = fake_build_file_contexts
mod.review_single_file_context = fake_review_single_file_context
mod.build_prompt = lambda *_args, **_kwargs: "aggregate repair prompt"
mod.hardened.openrouter_review = fake_hybrid_repair_review
try:
    hybrid_result, hybrid_model, _hybrid_tier = mod.openrouter_review_with_hybrid_first_pass(
        {"number": 402, "head": {"sha": "abc123"}},
        [{"filename": "docs/review.md", "status": "modified"}],
        hybrid_diff,
        schema,
        hybrid_config,
        hybrid_reporter,
        [],
        hybrid_line_index,
        "",
        "first-pass-deep",
        "one changed file",
        object(),
    )
finally:
    mod.build_file_contexts = original_build_file_contexts
    mod.review_single_file_context = original_review_single_file_context
    mod.build_prompt = original_build_prompt
    mod.hardened.openrouter_review = original_hybrid_openrouter_review

assert hybrid_model == "repair-model"
assert hybrid_result["_quality_retry_attempted"] is True
assert "summary indicated a possible issue" in hybrid_result["_quality_retry_reason"]
assert hybrid_result["_quality_retry_initial_summary"]
assert hybrid_result["_quality_retry_retry_summary"]
assert mod.split_findings_with_review_body_fallback(hybrid_result, hybrid_config, hybrid_line_index, hybrid_diff, []) == ([], [])
assert any(stage == "quality-retry" for stage, _detail in hybrid_reporter.updates)

workflow_source = (ROOT.parent / "workflows" / "reusable-openrouter-pr-review.yml").read_text(encoding="utf-8")
assert "dcoir_review_terminal_failure_v1" in workflow_source
assert 'exit "$review_exit_code"' in workflow_source

print("Pareto context DCOIR Review selftest passed")
