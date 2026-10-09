"""Canonical semantic-adjudication stage for DCOIR Review.

This module owns the bounded semantic adjudication pass that follows primary
and independent challenger review. Candidate hypotheses are treated as
untrusted evidence; the adjudicator may suppress, consolidate, or recover a
concrete defect, while exact-head verification remains authoritative before
publication.

Prompt, model projection, candidate digest/capping, and completion metadata are
owned here directly rather than by a historical numbered runtime overlay.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from dcoir_review import review_config
from dcoir_review import semantic_adjudication_quality_retry as quality_retry
from dcoir_review import semantic_adjudication_confidence as confidence_policy
from dcoir_review import semantic_evidence_hardening as semantic_evidence


FINAL_ADJUDICATION_COMPLETION_ATTR = "_semantic_adjudication_completion_token"
FINAL_ADJUDICATION_COMPLETION_TOKEN = object()
PROVIDER_RESULT_KEYS_ATTR = "_semantic_adjudication_provider_result_keys"
DEFAULT_ADJUDICATION_MODELS = review_config.DEFAULT_ADJUDICATION_MODELS
DEFAULT_ADJUDICATION_MAX_FINDINGS = review_config.DEFAULT_ADJUDICATION_MAX_FINDINGS
DEFAULT_CANDIDATE_DIGEST_CHARS = review_config.DEFAULT_CANDIDATE_DIGEST_CHARS

# Candidate hypotheses are supporting context, not the adjudicator's source of
# truth. Prefer a fair, compact representation of every hypothesis over a long
# representation of early candidates that silently drops later candidates.
CANDIDATE_DIGEST_PROFILES = (
    (220, 160, 400, 250),
    (200, 150, 300, 180),
    (180, 140, 220, 120),
    (160, 120, 140, 80),
    (120, 100, 80, 0),
)

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
  directly demonstrated defect in changed executable fixture, test, or benchmark
  code is publishable based on that code alone. Require consuming code or test
  wiring only when a claim depends on how the fixture is loaded, scored, or
  propagated, or on downstream production impact; documentation-only claims
  still require supplied evidence that the documented contract materially
  affects behavior.
- Anchor to the most relevant added executable/configuration line. Do not choose
  a blank or comment-only line when a relevant nonblank changed line exists.
- Preserve real Medium correctness findings; do not crowd them out merely
  because unrelated candidates used a High label.
- Keep the final set Pareto-small: at most {{max_findings}} findings. Returning
  fewer is better when those are the only demonstrable defects.

Required adversarial method:
{semantic_evidence.PREDICATE_AUDIT_BLOCK}

For each retained finding, use the normal review fields. Put the concrete
counterexample and code-path explanation in the finding body/validation text so
that the downstream verifier can independently test the claim.
""".strip()
ADJUDICATION_BLOCK = f"{ADJUDICATION_BLOCK}\n\n{confidence_policy.ADJUDICATION_CONFIDENCE_CONTRACT}".strip()



def adjudication_models(config: Any) -> list[str]:
    """Return the governed semantic-adjudicator model stack."""

    value = getattr(config, "semantic_adjudication_model_stack", None)
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(DEFAULT_ADJUDICATION_MODELS)


def _compact_candidate(
    index: int,
    item: dict[str, Any],
    path_chars: int,
    title_chars: int,
    body_chars: int,
    validation_chars: int,
) -> dict[str, Any]:
    return {
        "candidate": index,
        "path": str(item.get("path", "") or "")[:path_chars],
        "line": item.get("line", 0),
        "severity": str(item.get("severity", "") or "")[:16],
        "confidence": item.get("confidence", 0),
        "title": str(item.get("title", "") or "")[:title_chars],
        "body": str(item.get("body", "") or "")[:body_chars],
        "validation": str(item.get("validation", "") or "")[:validation_chars],
    }


def _candidate_digest(result: dict[str, Any], max_chars: int) -> tuple[str, int]:
    """Serialize every candidate as valid JSON while respecting the digest budget.

    Earlier v35 staging truncated the serialized JSON string after ``max_chars``.
    That biased the adjudicator toward early candidates and could cut the JSON in
    the middle of an object. Instead, progressively compact every candidate so
    candidate order never determines whether a hypothesis is visible.
    """

    findings = result.get("findings", []) if isinstance(result, dict) else []
    if not isinstance(findings, list):
        findings = []
    valid_findings = [item for item in findings if isinstance(item, dict)]
    count = len(valid_findings)

    for path_chars, title_chars, body_chars, validation_chars in CANDIDATE_DIGEST_PROFILES:
        compact = [
            _compact_candidate(
                index,
                item,
                path_chars,
                title_chars,
                body_chars,
                validation_chars,
            )
            for index, item in enumerate(valid_findings, start=1)
        ]
        text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(text) <= max_chars:
            return text, count

    # Last-resort identity digest still preserves every candidate and remains
    # valid JSON. If even this cannot fit, fail explicitly instead of silently
    # hiding a tail of the candidate set from adjudication.
    identity = [
        {
            "candidate": index,
            "path": str(item.get("path", "") or "")[:80],
            "line": item.get("line", 0),
            "title": str(item.get("title", "") or "")[:60],
        }
        for index, item in enumerate(valid_findings, start=1)
    ]
    text = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    if len(text) > max_chars:
        raise ValueError(
            f"DCOIR semantic-adjudication candidate digest budget {max_chars} is too small to represent all {count} candidates"
        )
    return text, count


def _cap_adjudicated_findings(module: Any, result: dict[str, Any], limit: int) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise module.hardened.ReviewQualityError("DCOIR semantic adjudicator returned a non-object result")
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        raise module.hardened.ReviewQualityError("DCOIR semantic adjudicator returned a non-list findings value")
    if len(findings) <= limit:
        return result
    capped = dict(result)
    capped["findings"] = module.rank_findings_for_required_budget(
        [item for item in findings if isinstance(item, dict)], limit
    )
    capped["_semantic_adjudication_overflow_trimmed"] = len(findings) - len(capped["findings"])
    return capped


def build_semantic_adjudication_stage(module: Any, next_review: Any) -> Any:
    original = next_review
    if not callable(original):
        raise RuntimeError("DCOIR semantic adjudication requires a callable hybrid review stage")

    def semantic_adjudication_stage(
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
        models = adjudication_models(config)
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
        max_prompt_chars = max(0, int(getattr(config, "max_prompt_chars", 120000)))
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
            if max_prompt_chars <= len(marker):
                prompt = marker[:max_prompt_chars]
            else:
                prompt = prompt[: max_prompt_chars - len(marker)] + marker

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
        provider_result_keys = tuple(sorted(adjudicated.keys())) if isinstance(adjudicated, dict) else ()
        from dcoir_review import semantic_adjudication_normalization

        adjudicated = semantic_adjudication_normalization.normalize_adjudicator_result(module, adjudicated)
        adjudicated = _cap_adjudicated_findings(module, adjudicated, max_findings)

        adjudicated, retry_model, retry_tier = quality_retry.retry_rejected_adjudication(
            module, adjudicated, config, risk_sentinels, line_index, prompt, schema,
            adjudication_config, reporter, max_findings, _cap_adjudicated_findings,
            semantic_adjudication_normalization.normalize_adjudicator_result,
        )
        if retry_model:
            adjudicator_model, adjudicator_tier = retry_model, retry_tier
        adjudicated[PROVIDER_RESULT_KEYS_ATTR] = provider_result_keys
        adjudicated["_semantic_adjudication_attempted"] = True
        adjudicated["_semantic_adjudication_model"] = adjudicator_model
        adjudicated["_semantic_adjudication_input_candidates"] = candidate_count
        adjudicated["_semantic_adjudication_output_findings"] = len(
            module.hardened.result_findings(adjudicated)
        )
        adjudicated[FINAL_ADJUDICATION_COMPLETION_ATTR] = FINAL_ADJUDICATION_COMPLETION_TOKEN
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

    return semantic_adjudication_stage



__all__ = [
    "ADJUDICATION_BLOCK",
    "CANDIDATE_DIGEST_PROFILES",
    "DEFAULT_ADJUDICATION_MAX_FINDINGS",
    "DEFAULT_ADJUDICATION_MODELS",
    "DEFAULT_CANDIDATE_DIGEST_CHARS",
    "FINAL_ADJUDICATION_COMPLETION_ATTR",
    "FINAL_ADJUDICATION_COMPLETION_TOKEN",
    "PROVIDER_RESULT_KEYS_ATTR",
    "_candidate_digest",
    "_cap_adjudicated_findings",
    "adjudication_models",
    "build_semantic_adjudication_stage",
]
