"""DCOIR Review v35 semantic adjudication and falsification-first verification.

Issue #456 showed that frontier per-file detection plus an independent whole-PR
challenger materially improves recall, but the union can still contain dozens of
partially overlapping or speculative hypotheses.  Sending that union directly
to ranking and one-by-one verification makes final quality depend too heavily on
severity sorting and consumes verifier budget on candidates that a strong
reviewer would first consolidate or disprove.

v35 inserts one bounded semantic adjudication pass after the existing primary +
challenger review and before normalization/publication verification.  The
adjudicator treats detector output as untrusted hypotheses, independently audits
the changed contracts, may recover a demonstrable miss that neither detector
named, collapses duplicate variants to root causes, and must provide concrete
counterexamples rather than speculative warnings.  v35 also makes the existing
v21 verifier explicitly falsification-first.

This overlay does not increase the inline publication ceiling, does not weaken
v21 exact-head evidence requirements, and adds no branch-write, commit, or
autonomous remediation capability.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v34 as v34


VERSION = "v35"
APPLIED_MARKER = "_dcoir_review_v35_applied"
CONFIG_STORAGE = "_dcoir_review_v35_original_load_pareto_context_config"
HYBRID_STORAGE = "_dcoir_review_v35_original_hybrid_first_pass"
VERIFIER_PROMPT_STORAGE = "_dcoir_review_v35_original_verifier_prompt"
DEFAULT_ADJUDICATION_MODELS = ("anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro")
DEFAULT_ADJUDICATION_MAX_FINDINGS = 8
DEFAULT_CANDIDATE_DIGEST_CHARS = 24000

ADJUDICATION_BLOCK = f"""
Final semantic adjudication pass.

The candidate list below comes from earlier reviewers. Treat every candidate as
an untrusted hypothesis, not as a fact and not as a checklist you must preserve.
Independently inspect the supplied changed PR evidence before deciding what is
real. You MAY add a high-confidence defect that the candidate list missed when
the supplied changed code directly demonstrates it.

Publication-quality rules:
- Return only distinct root-cause defects that can change runtime, validation,
  safety, correctness, governance, or material operator behavior.
- For every retained finding, be able to state a concrete minimal input or
  counterexample that triggers the defect and the exact predicate/control-flow
  path that lets the bad behavior pass or the valid behavior fail.
- Actively try to disprove each hypothesis. Check surrounding guards, sibling
  branches, tests, and consuming code in the supplied evidence before retaining
  it. If the claim needs an unseen loader/runtime assumption, drop it.
- Collapse multiple manifestations of one implementation defect into one root
  cause. Keep separate findings only when they require materially different code
  changes.
- Prefer executable changed code over fixture/documentation speculation. A
  fixture or documentation finding is publishable only when supplied consuming
  code or test wiring demonstrates the concrete misbehavior.
- Anchor to the most relevant added executable/configuration line. Do not choose
  a blank or comment-only line when a relevant nonblank changed line exists.
- Preserve real Medium correctness findings; do not crowd them out merely
  because unrelated candidates used a High label.
- Keep the final set Pareto-small: at most {{max_findings}} findings. Returning
  fewer is better when those are the only demonstrable defects.

Required adversarial method:
{v34.PREDICATE_AUDIT_BLOCK}

For each retained finding, use the normal review fields. Put the concrete
counterexample and code-path explanation in the finding body/validation text so
that the downstream verifier can independently test the claim.
""".strip()

VERIFIER_FALSIFICATION_BLOCK = """
Falsification-first verification requirements:
- Treat the candidate as an adversarial hypothesis and first try to prove it false.
- Set supported=true only when the supplied exact-head code permits a concrete minimal input/counterexample that triggers the claimed bad behavior.
- Your evidence must identify the relevant predicate/control-flow path and explain why surrounding guards in the supplied file do not block that counterexample.
- If the claim depends on an unseen loader, another unseen file, an assumed runtime convention, or fixture semantics not demonstrated by supplied consuming code, set supported=false.
- Do not support a finding merely because the proposed fix would be reasonable; verify defect presence, not fix desirability.
""".strip()


def _as_string_list(value: Any, fallback: tuple[str, ...]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback)


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, parsed)


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v35 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.semantic_adjudication_review = module.hardened.bool_value(
            data, "semantic_adjudication_review", True
        )
        config.semantic_adjudication_model_stack = _as_string_list(
            data.get("semantic_adjudication_model_stack"), DEFAULT_ADJUDICATION_MODELS
        )
        configured_max = _positive_int(
            data.get("semantic_adjudication_max_findings", DEFAULT_ADJUDICATION_MAX_FINDINGS),
            DEFAULT_ADJUDICATION_MAX_FINDINGS,
        )
        inline_max = _positive_int(getattr(config, "max_inline_comments", configured_max), configured_max)
        config.semantic_adjudication_max_findings = min(configured_max, inline_max)
        config.semantic_adjudication_candidate_digest_chars = _positive_int(
            data.get("semantic_adjudication_candidate_digest_chars", DEFAULT_CANDIDATE_DIGEST_CHARS),
            DEFAULT_CANDIDATE_DIGEST_CHARS,
        )
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _candidate_digest(result: dict[str, Any], max_chars: int) -> tuple[str, int]:
    findings = result.get("findings", []) if isinstance(result, dict) else []
    if not isinstance(findings, list):
        findings = []
    compact: list[dict[str, Any]] = []
    for index, item in enumerate(findings, start=1):
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "candidate": index,
                "path": str(item.get("path", "") or "")[:240],
                "line": item.get("line", 0),
                "severity": str(item.get("severity", "") or "")[:24],
                "confidence": item.get("confidence", 0),
                "title": str(item.get("title", "") or "")[:180],
                "body": str(item.get("body", "") or "")[:700],
                "validation": str(item.get("validation", "") or "")[:500],
            }
        )
    text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(text) > max_chars:
        marker = "...<candidate digest truncated>"
        text = text[: max(0, max_chars - len(marker))] + marker
    return text, len(compact)


def _cap_adjudicated_findings(module: Any, result: dict[str, Any], limit: int) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise module.hardened.ReviewQualityError("DCOIR v35 adjudicator returned a non-object result")
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        raise module.hardened.ReviewQualityError("DCOIR v35 adjudicator returned a non-list findings value")
    if len(findings) <= limit:
        return result
    capped = dict(result)
    capped["findings"] = module.rank_findings_for_required_budget(
        [item for item in findings if isinstance(item, dict)], limit
    )
    capped["_semantic_adjudication_overflow_trimmed"] = len(findings) - len(capped["findings"])
    return capped


def _patch_semantic_adjudication(module: Any) -> None:
    original = getattr(module, HYBRID_STORAGE, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, HYBRID_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v35 could not locate active hybrid review function")

    def openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        detector_result, detector_model, detector_tier = original(
            pr,
            files,
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )

        if not bool(getattr(config, "semantic_adjudication_review", True)) or review_mode not in {
            "first-pass-deep",
            "deep-forced",
        }:
            return detector_result, detector_model, detector_tier

        max_findings = int(getattr(config, "semantic_adjudication_max_findings", DEFAULT_ADJUDICATION_MAX_FINDINGS))
        digest_chars = int(
            getattr(config, "semantic_adjudication_candidate_digest_chars", DEFAULT_CANDIDATE_DIGEST_CHARS)
        )
        digest, candidate_count = _candidate_digest(detector_result, digest_chars)

        adjudication_config = copy.copy(config)
        models = _as_string_list(
            getattr(config, "semantic_adjudication_model_stack", None), DEFAULT_ADJUDICATION_MODELS
        )
        adjudication_config.model_stack = models
        adjudication_config.model = models[0]

        instruction = ADJUDICATION_BLOCK.format(max_findings=max_findings)
        visible_digest = module.base.sanitize_text(digest, config)
        prefix = (
            f"{instruction}\n\n"
            "Candidate hypotheses from the earlier detector/challenger stages:\n"
            f"```json\n{visible_digest}\n```\n\n"
            "Independently adjudicate those hypotheses against the PR evidence below.\n\n"
        )
        max_prompt_chars = int(getattr(config, "max_prompt_chars", 120000))
        evidence_budget = max(20000, max_prompt_chars - len(prefix) - 1000)
        evidence_config = copy.copy(config)
        evidence_config.max_prompt_chars = evidence_budget
        aggregate_prompt = module.build_prompt(
            pr,
            files,
            diff,
            evidence_config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
        )
        prompt = prefix + aggregate_prompt
        if len(prompt) > max_prompt_chars:
            marker = "\n\n[semantic adjudication PR evidence truncated by reviewer budget]"
            prompt = prompt[: max(0, max_prompt_chars - len(marker))] + marker

        module.hardened.write_debug_text_artifact_safely(
            config, "prompts/06-semantic-adjudication-prompt.txt", prompt
        )
        if reporter:
            reporter.update(
                "semantic-adjudication",
                f"adjudicating {candidate_count} detector/challenger hypotheses with {models[0]}",
            )

        adjudicated, adjudicator_model, adjudicator_tier = module.hardened.openrouter_review(
            prompt, schema, adjudication_config, reporter
        )
        adjudicated = _cap_adjudicated_findings(module, adjudicated, max_findings)
        adjudicated["_semantic_adjudication_attempted"] = True
        adjudicated["_semantic_adjudication_model"] = adjudicator_model
        adjudicated["_semantic_adjudication_input_candidates"] = candidate_count
        adjudicated["_semantic_adjudication_output_findings"] = len(
            module.hardened.result_findings(adjudicated)
        )
        module.hardened.write_debug_json_artifact_safely(
            config,
            "responses/06-semantic-adjudication-result.json",
            {
                "detector_model": detector_model,
                "adjudicator_model": adjudicator_model,
                "service_tier": adjudicator_tier,
                "input_candidate_count": candidate_count,
                "output_finding_count": len(module.hardened.result_findings(adjudicated)),
                "result": adjudicated,
            },
        )
        if reporter:
            reporter.update(
                "semantic-adjudication",
                (
                    f"input={candidate_count}; retained={len(module.hardened.result_findings(adjudicated))}; "
                    f"served={adjudicator_model}"
                ),
            )
        model_label = f"{detector_model}; semantic-adjudicator={adjudicator_model}"
        tier_parts = [str(detector_tier or "").strip(), str(adjudicator_tier or "").strip()]
        tier_label = ", ".join(item for item in tier_parts if item)
        return adjudicated, model_label, tier_label

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def _patch_verifier_prompt() -> None:
    original = getattr(v21, VERIFIER_PROMPT_STORAGE, None)
    if original is None:
        original = getattr(v21, "_verifier_prompt", None)
        if callable(original):
            setattr(v21, VERIFIER_PROMPT_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v35 could not locate v21 verifier prompt builder")

    def _verifier_prompt(finding, path, line, line_text, file_text, base, config):
        prompt = str(original(finding, path, line, line_text, file_text, base, config))
        combined = f"{prompt}\n\n{VERIFIER_FALSIFICATION_BLOCK}"
        return base.sanitize_text(combined, config)

    v21._verifier_prompt = _verifier_prompt


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_config_loader(module)
    _patch_semantic_adjudication(module)
    _patch_verifier_prompt()
    setattr(module, APPLIED_MARKER, True)
