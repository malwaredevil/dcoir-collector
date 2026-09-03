#!/usr/bin/env python3
"""Offline planner/context regressions for Architecture-B escalation v44."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v44 as v44
import dcoir_review_required_runtime_patch_v44_scope as scope
from dcoir_review.entrypoint import DcoirReviewEntrypoint


ROOT = Path(__file__).resolve().parent.parent


def finding(
    *,
    path: str = "src/app.py",
    line: int = 7,
    confidence: float = 0.95,
    severity: str = "medium",
    title: str = "Candidate",
    body: str = "Exact changed-line evidence.",
) -> dict[str, object]:
    return {
        "path": path,
        "line": line,
        "confidence": confidence,
        "severity": severity,
        "title": title,
        "body": body,
        "validation": "python3 -m py_compile src/app.py",
    }


def planner_module(uncovered=None):
    return SimpleNamespace(
        hardened=SimpleNamespace(
            result_findings=lambda result: result.get("findings", []),
            uncovered_risk_sentinels=lambda _findings, _sentinels, _config: list(
                uncovered or []
            ),
        )
    )


def config(**updates):
    values = {
        "minimum_confidence": 0.70,
        "candidate_escalation_confidence_margin": 0.10,
        "candidate_escalation_max_paths": 4,
        "candidate_escalation_file_chars": 12000,
        "candidate_escalation_total_context_chars": 48000,
        "per_file_review_max_files": 100,
    }
    values.update(updates)
    return SimpleNamespace(**values)


FILES = [
    {"filename": "src/app.py", "status": "modified", "patch": "+safe = True"},
    {"filename": "src/helper.py", "status": "modified", "patch": "+value = 1"},
]


def plan(items, *, mode="first-pass-deep", module=None, cfg=None):
    return scope.build_escalation_plan(
        module or planner_module(),
        {"findings": items},
        FILES,
        [],
        cfg or config(),
        mode,
    )


def test_planner_contract() -> None:
    low_risk = plan([finding()])
    assert low_risk["mode"] == "none"
    assert low_risk["reasons"] == ["confident-low-risk-primary-evidence"]

    near = plan([finding(confidence=0.79)])
    assert near["mode"] == "candidate-scoped"
    assert "near-publication-threshold" in near["reasons"]

    high = plan([finding(severity="high")])
    assert high["mode"] == "candidate-scoped"
    assert "high-risk-severity" in high["reasons"]

    sentinel = SimpleNamespace(path="src/app.py")
    deterministic_disagreement = plan([], module=planner_module([sentinel]))
    assert deterministic_disagreement["mode"] == "candidate-scoped"
    assert deterministic_disagreement["uncovered_risk_paths"] == ["src/app.py"]
    assert "uncovered-required-risk-sentinel" in deterministic_disagreement["reasons"]

    cross_file = plan(
        [finding(body="The caller in src/helper.py still violates this contract.")]
    )
    assert cross_file["mode"] == "candidate-scoped"
    assert cross_file["selected_paths"] == ["src/app.py", "src/helper.py"]
    assert "explicit-cross-file-dependency" in cross_file["reasons"]

    conflict = plan(
        [finding(title="First hypothesis"), finding(title="Conflicting hypothesis")]
    )
    assert conflict["mode"] == "candidate-scoped"
    assert "conflicting-candidate-hypotheses" in conflict["reasons"]

    unresolved = plan([finding(body="The unseen caller violates this contract.")])
    assert unresolved["mode"] == "broader-context"
    assert len(unresolved["escalated_candidate_keys"]) == 1
    assert unresolved["reasons"] == ["unresolved-cross-file-dependency"]

    ambiguous = plan([finding(path="src/missing.py")])
    assert ambiguous["mode"] == "broader-context"
    assert len(ambiguous["escalated_candidate_keys"]) == 1
    assert ambiguous["reasons"] == ["candidate-anchor-ambiguous"]

    forced = plan([finding()], mode="deep-forced")
    assert forced["mode"] == "full-deep"
    assert forced["reasons"] == ["explicit-deep-mode"]

    unsupported = plan([finding()], mode="diff")
    assert unsupported["mode"] == "not-applicable"
    assert unsupported["reasons"] == ["review-mode-not-deep"]

    invalid = plan([finding()], cfg=config(candidate_escalation_max_paths="bad"))
    assert invalid["mode"] == "broader-context"
    assert invalid["reasons"] == ["invalid-escalation-path-budget"]


def test_deduplication_and_shape() -> None:
    duplicate = finding(title=" Same   title ")
    duplicate_again = {**duplicate, "title": "same title", "body": "different prose"}
    unique = finding(line=8, title="Same title")
    deduped = scope.dedupe_exact_findings([duplicate, duplicate_again, unique])
    assert len(deduped) == 2
    selected, passthrough = scope.scoped_findings(
        [duplicate, unique], {"src/app.py"}
    )
    assert len(selected) == 2 and passthrough == []
    digest = scope.candidate_digest(deduped, 2000)
    assert '"path":"src/app.py"' in digest
    assert '"line":8' in digest


def test_bounded_exact_head_evidence() -> None:
    debug = {}
    module = SimpleNamespace(
        build_file_contexts=lambda _gh, _pr, files, _cfg: [
            {"path": item["filename"], "text": f"content for {item['filename']}"}
            for item in files
        ],
        base=SimpleNamespace(
            sanitize_text=lambda value, _cfg: str(value),
            sanitized_prompt_value=lambda value, _cfg: str(value),
        ),
        hardened=SimpleNamespace(
            risk_sentinel_block=lambda _items, _cfg: "risk evidence",
            write_debug_json_artifact_safely=lambda _cfg, name, value: debug.__setitem__(
                name, value
            ),
        ),
    )
    pr = {
        "number": 470,
        "title": "Scoped evidence",
        "head": {"sha": "a" * 40},
    }
    evidence, reason = scope.build_bounded_evidence(
        module, SimpleNamespace(), pr, FILES, config(), [], {"src/app.py"}
    )
    assert reason == ""
    assert evidence is not None
    assert "Exact reviewed HEAD: " + "a" * 40 in evidence
    assert "### Scoped file: src/app.py" in evidence
    assert "src/helper.py" not in evidence

    missing_module = SimpleNamespace(
        **{**vars(module), "build_file_contexts": lambda *_args: []}
    )
    missing, reason = scope.build_bounded_evidence(
        missing_module,
        SimpleNamespace(),
        pr,
        FILES,
        config(),
        [],
        {"src/app.py"},
    )
    assert missing is None and reason == "selected-head-context-unavailable"


def test_config_and_registration() -> None:
    parsed = {
        "candidate_scoped_escalation_review": True,
        "candidate_escalation_confidence_margin": 0.08,
        "candidate_escalation_max_paths": 3,
        "candidate_escalation_file_chars": 9000,
        "candidate_escalation_total_context_chars": 30000,
    }
    module = SimpleNamespace(
        load_pareto_context_config=lambda _path: SimpleNamespace(),
        hardened=SimpleNamespace(
            parse_yaml_like_data=lambda _path: parsed,
            bool_value=lambda data, key, default: data.get(key, default),
        ),
    )
    v44._patch_config_loader(module)
    loaded = module.load_pareto_context_config("unused.yml")
    assert loaded.candidate_scoped_escalation_review is True
    assert loaded.candidate_escalation_confidence_margin == 0.08
    assert loaded.candidate_escalation_max_paths == 3
    assert loaded.candidate_escalation_file_chars == 9000
    assert loaded.candidate_escalation_total_context_chars == 30000

    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review_required_runtime_patch_v45",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "candidate_scoped_escalation_review: true" in production
    assert "dcoir_review_required_runtime_patch_v44_scope_selftest.py" in production
    assert "dcoir_review_required_runtime_patch_v44_selftest.py" in production
    review_module = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(review_module)
    production_config = review_module.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )
    assert production_config.candidate_scoped_escalation_review is True
    assert production_config.candidate_escalation_confidence_margin == 0.10
    assert production_config.candidate_escalation_max_paths == 4
    assert production_config.candidate_escalation_file_chars == 12000
    assert production_config.candidate_escalation_total_context_chars == 48000


def main() -> None:
    test_planner_contract()
    test_deduplication_and_shape()
    test_bounded_exact_head_evidence()
    test_config_and_registration()
    print("dcoir_review_required_runtime_patch_v44_scope_selftest passed")


if __name__ == "__main__":
    main()
