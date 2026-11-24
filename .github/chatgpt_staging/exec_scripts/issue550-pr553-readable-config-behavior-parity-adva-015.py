from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "781a480bb306ff7e0bf1fd55302636a0176ad5c5"
EXPECTED_TREE = "ecfe9870cff993695d58c9ee8f35525a0ccd9902"
EXPECTED_PATCH_SHA = "923ffd839b1bacb4cf2a2801a0916bae783d7470e2c320cf1804740b48302cb1"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-readable-config-behavior-parity-adva-015"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-strong-loader-guard-preview-013.py"
patch = downloads / "issue550-pr553-readable-config-strong-loader-guard-preview-013.patch"
old_wt = downloads / f"{REQUEST_ID}-old"
new_wt = downloads / f"{REQUEST_ID}-new"
probe_path = downloads / f"{REQUEST_ID}-probe.py"
summary_path = downloads / f"{REQUEST_ID}-summary.txt"
results_path = downloads / f"{REQUEST_ID}-results.json"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def run(*args: str, cwd: Path | None = None, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True, env=env)
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode:
        raise RuntimeError(f"command failed {completed.returncode}: {args}")
    return completed


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"config replacement anchor count for {old!r}: {text.count(old)}")
    return text.replace(old, new, 1)


run(sys.executable, str(preview), cwd=repo)
if not patch.is_file():
    raise RuntimeError("strong-guard readable patch missing")
patch_sha = hashlib.sha256(patch.read_bytes()).hexdigest()
if patch_sha != EXPECTED_PATCH_SHA:
    raise RuntimeError(f"strong-guard patch drift: {patch_sha}")

run("git", "-C", str(repo), "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
head = run("git", "-C", str(repo), "rev-parse", f"refs/remotes/origin/{BRANCH}").stdout.strip()
if head != EXPECTED_HEAD:
    raise RuntimeError(f"source head drift: {head}")
tree = run("git", "-C", str(repo), "rev-parse", f"{EXPECTED_HEAD}^{{tree}}").stdout.strip()
if tree != EXPECTED_TREE:
    raise RuntimeError(f"source tree drift: {tree}")

for wt in (old_wt, new_wt):
    if wt.exists():
        run("git", "-C", str(repo), "worktree", "remove", "--force", str(wt), check=False)
    run("git", "-C", str(repo), "worktree", "add", "--detach", str(wt), EXPECTED_HEAD)
run("git", "apply", "--check", str(patch), cwd=new_wt)
run("git", "apply", str(patch), cwd=new_wt)

probe = r'''from __future__ import annotations
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
scripts = root / ".github" / "dcoir_review" / "scripts"
sys.path.insert(0, str(scripts))
from dcoir_review.entrypoint import DcoirReviewEntrypoint
entry = DcoirReviewEntrypoint()
module = entry.import_module(entry.review_module_name)
entry.apply_runtime_patches(module)
attrs = (
    "adversarial_confirmation_review", "adversarial_confirmation_model_stack", "review_reasoning_effort",
    "dcoir_v32_verifier_repair_limit", "semantic_adjudication_review", "semantic_adjudication_model_stack",
    "semantic_adjudication_max_findings", "semantic_adjudication_candidate_digest_chars",
    "candidate_scoped_escalation_review", "candidate_escalation_confidence_margin",
    "candidate_escalation_max_paths", "candidate_escalation_file_chars", "candidate_escalation_total_context_chars",
    "verifier_authoritative_publication_review", "canonical_semantic_context_review",
    "adaptive_semantic_budgets_review", "adaptive_semantic_min_prompt_chars",
    "adaptive_semantic_small_delta_prompt_chars", "adaptive_semantic_small_delta_max_files",
    "adaptive_semantic_small_delta_max_diff_chars", "adaptive_semantic_small_delta_max_context_chars",
    "verified_finding_gate_state_review", "semantic_candidate_identity_review",
    "per_file_review_model_stack", "per_file_review_reasoning_effort", "per_file_review_max_tokens",
    "per_file_review_provider_sort", "repair_critic_batching_enabled", "repair_critic_batch_max_findings",
)
try:
    config = module.load_pareto_context_config(str(config_path))
    from dcoir_review import finding_verifier, repair_pipeline
    result = {"status": "ok", "loader_module": module.load_pareto_context_config.__module__}
    for name in attrs:
        result[name] = getattr(config, name, "__MISSING__")
    result["VERIFIER_MAX_MODEL_FINDINGS"] = finding_verifier.VERIFIER_MAX_MODEL_FINDINGS
    result["MAX_REPAIR_CANDIDATES"] = repair_pipeline.MAX_REPAIR_CANDIDATES
    sink = getattr(config, "_dcoir_v54_run_telemetry_sink", None)
    result["telemetry_sink_type"] = type(sink).__name__ if sink is not None else None
    result["telemetry_error_count"] = getattr(config, "_dcoir_v54_telemetry_error_count", 0)
except Exception as exc:
    result = {"status": "error", "type": type(exc).__name__, "message": str(exc)}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
'''
probe_path.write_text(probe, encoding="utf-8", newline="\n")

base_config = (old_wt / ".github/dcoir_review/openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")

valid = base_config
for old, new in (
    ("\nmax_inline_comments: 12\n", "\nmax_inline_comments: 5\n"),
    ("\nper_file_review_reasoning_effort: high\n", "\nper_file_review_reasoning_effort: medium\n"),
    ("\nper_file_review_max_tokens: 32768\n", "\nper_file_review_max_tokens: 12345\n"),
    ("\nper_file_review_provider_sort: price\n", "\nper_file_review_provider_sort: throughput\n"),
    ("\nadversarial_confirmation_review: true\n", "\nadversarial_confirmation_review: false\n"),
    ("\nreview_reasoning_effort: xhigh\n", "\nreview_reasoning_effort: high\n"),
    ("\nsemantic_adjudication_review: true\n", "\nsemantic_adjudication_review: false\n"),
    ("\nsemantic_adjudication_max_findings: 8\n", "\nsemantic_adjudication_max_findings: 3\n"),
    ("\nsemantic_adjudication_candidate_digest_chars: 24000\n", "\nsemantic_adjudication_candidate_digest_chars: 12345\n"),
    ("\ncandidate_scoped_escalation_review: true\n", "\ncandidate_scoped_escalation_review: false\n"),
    ("\ncandidate_escalation_confidence_margin: 0.10\n", "\ncandidate_escalation_confidence_margin: 0.25\n"),
    ("\ncandidate_escalation_max_paths: 4\n", "\ncandidate_escalation_max_paths: 2\n"),
    ("\ncandidate_escalation_file_chars: 12000\n", "\ncandidate_escalation_file_chars: 2222\n"),
    ("\ncandidate_escalation_total_context_chars: 48000\n", "\ncandidate_escalation_total_context_chars: 5555\n"),
    ("\nverifier_authoritative_publication_review: true\n", "\nverifier_authoritative_publication_review: false\n"),
    ("\nverified_finding_gate_state_review: true\n", "\nverified_finding_gate_state_review: false\n"),
    ("\nsemantic_candidate_identity_review: true\n", "\nsemantic_candidate_identity_review: false\n"),
    ("\ncanonical_semantic_context_review: true\n", "\ncanonical_semantic_context_review: false\n"),
    ("\nadaptive_semantic_budgets_review: true\n", "\nadaptive_semantic_budgets_review: false\n"),
    ("\nadaptive_semantic_min_prompt_chars: 48000\n", "\nadaptive_semantic_min_prompt_chars: 11111\n"),
    ("\nadaptive_semantic_small_delta_prompt_chars: 60000\n", "\nadaptive_semantic_small_delta_prompt_chars: 22222\n"),
    ("\nadaptive_semantic_small_delta_max_files: 4\n", "\nadaptive_semantic_small_delta_max_files: 2\n"),
    ("\nadaptive_semantic_small_delta_max_diff_chars: 20000\n", "\nadaptive_semantic_small_delta_max_diff_chars: 3333\n"),
    ("\nadaptive_semantic_small_delta_max_context_chars: 30000\n", "\nadaptive_semantic_small_delta_max_context_chars: 4444\n"),
    ("\nfix_synthesis_max_findings: 8\n", "\nfix_synthesis_max_findings: 7\n"),
    ("\nrepair_critic_batching_enabled: true\n", "\nrepair_critic_batching_enabled: false\n"),
    ("\nrepair_critic_batch_max_findings: 8\n", "\nrepair_critic_batch_max_findings: 3\n"),
):
    valid = replace_once(valid, old, new)

tolerant = base_config
for old, new in (
    ("\nsemantic_adjudication_max_findings: 8\n", "\nsemantic_adjudication_max_findings: not-an-int\n"),
    ("\nsemantic_adjudication_candidate_digest_chars: 24000\n", "\nsemantic_adjudication_candidate_digest_chars: nope\n"),
    ("\ncandidate_escalation_confidence_margin: 0.10\n", "\ncandidate_escalation_confidence_margin: 2.0\n"),
    ("\ncandidate_escalation_max_paths: 4\n", "\ncandidate_escalation_max_paths: 0\n"),
    ("\ncandidate_escalation_file_chars: 12000\n", "\ncandidate_escalation_file_chars: bad\n"),
    ("\nadaptive_semantic_min_prompt_chars: 48000\n", "\nadaptive_semantic_min_prompt_chars: bad\n"),
):
    tolerant = replace_once(tolerant, old, new)

strict_batch = replace_once(base_config, "\nrepair_critic_batch_max_findings: 8\n", "\nrepair_critic_batch_max_findings: invalid\n")
strict_per_file = replace_once(base_config, "\nper_file_review_max_tokens: 32768\n", "\nper_file_review_max_tokens: 0\n")

cases = {
    "default": base_config,
    "custom_valid": valid,
    "tolerant_invalid": tolerant,
    "strict_invalid_batch": strict_batch,
    "strict_invalid_per_file": strict_per_file,
}
results: dict[str, dict[str, object]] = {}
try:
    for case_name, case_text in cases.items():
        case_results = {}
        for label, wt in (("old", old_wt), ("new", new_wt)):
            config_path = wt / f".github/dcoir_review/{REQUEST_ID}-{case_name}.yml"
            config_path.write_text(case_text, encoding="utf-8", newline="\n")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(wt / ".github/dcoir_review/scripts")
            process = run(sys.executable, str(probe_path), str(wt), str(config_path), cwd=wt, env=env)
            parsed = json.loads(process.stdout.strip().splitlines()[-1])
            case_results[label] = parsed
        old_result = case_results["old"]
        new_result = case_results["new"]
        # The loader callable owner is intentionally different after consolidation;
        # compare behavior after removing only that expected architectural delta.
        old_compare = dict(old_result)
        new_compare = dict(new_result)
        old_compare.pop("loader_module", None)
        new_compare.pop("loader_module", None)
        if old_compare != new_compare:
            raise RuntimeError(
                f"behavior parity mismatch for {case_name}:\nOLD={json.dumps(old_compare, sort_keys=True)}\nNEW={json.dumps(new_compare, sort_keys=True)}"
            )
        results[case_name] = case_results
finally:
    for wt in (old_wt, new_wt):
        run("git", "-C", str(repo), "worktree", "remove", "--force", str(wt), check=False)

if results["strict_invalid_batch"]["old"].get("status") != "error":
    raise RuntimeError("strict batch invalid case did not fail")
if results["strict_invalid_per_file"]["old"].get("status") != "error":
    raise RuntimeError("strict per-file invalid case did not fail")
for case_name in ("default", "custom_valid", "tolerant_invalid"):
    if results[case_name]["old"].get("status") != "ok":
        raise RuntimeError(f"expected successful parity case failed: {case_name}")

results_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
summary = [
    "result=PASS",
    f"exact_head={EXPECTED_HEAD}",
    f"exact_tree={EXPECTED_TREE}",
    f"source_patch_sha256={patch_sha}",
    "parity_cases=5",
    "default_parity=pass",
    "custom_valid_parity=pass",
    "tolerant_invalid_parity=pass",
    "strict_invalid_batch_parity=pass",
    "strict_invalid_per_file_parity=pass",
    "telemetry_sink_parity=pass",
    "verifier_repair_side_effect_parity=pass",
    "no_inference=true",
    "no_provider_calls=true",
]
summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")
print(summary_path.read_text(encoding="utf-8"), end="")
print("ISSUE550_PR553_READABLE_CONFIG_BEHAVIOR_PARITY_ADVA_015_PASS")
