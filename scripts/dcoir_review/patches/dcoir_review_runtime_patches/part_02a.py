

def _patch_pareto_globals(globals_dict: dict[str, Any]) -> None:
    base = globals_dict.get("base")
    if base is not None:
        _patch_base_formatter_module(base)

    globals_dict["is_python_dynamic_exec_fix_scope"] = _patched_dynamic_exec_scope

    original_dedupe_key = globals_dict.get("finding_dedupe_key")
    if callable(original_dedupe_key):

        def patched_finding_dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
            kind = _semantic_kind(finding)
            path = str(finding.get("path", "") or "").strip()
            line = "" if kind == "yaml_broad_write" else str(finding.get("line", "") or "").strip()
            if kind:
                return (path, line, kind, "")
            return original_dedupe_key(finding)

        globals_dict["finding_dedupe_key"] = patched_finding_dedupe_key

    hardened = globals_dict.get("hardened")
    if hardened is None:
        return

    original_synthesize = globals_dict.get("synthesize_fix_for_finding")
    if callable(original_synthesize):
        build_prompt = globals_dict.get("build_fix_synthesis_prompt")
        file_line_text = globals_dict.get("file_line_text")
        safe_artifact_name = globals_dict.get("safe_artifact_name")
        verified_suggestion = globals_dict.get("verified_suggested_replacement")
        harden_dynamic = globals_dict.get("harden_python_dynamic_exec_fix_result")

        def patched_synthesize_fix_for_finding(
            index: int,
            finding: dict[str, Any],
            file_text: str,
            schema: dict[str, Any],
            config: Any,
        ) -> dict[str, Any]:
            path = str(finding.get("path", "") or "").strip()
            line = int(finding.get("line", 0) or 0)
            line_text = file_line_text(file_text, line) if callable(file_line_text) else ""
            if not path or not line_text or not callable(build_prompt):
                return original_synthesize(index, finding, file_text, schema, config)
            prompt = build_prompt(finding, path, line, line_text, file_text, config)
            artifact_id = safe_artifact_name(f"{path}-{line}", f"fix-{index:02d}") if callable(safe_artifact_name) else f"fix-{index:02d}"
            hardened.write_debug_text_artifact_safely(config, f"prompts/fix-synthesis/{index:02d}-{artifact_id}.txt", prompt)
            result, model_used, service_tier = hardened.openrouter_review(prompt, schema, config, reporter=None)
            repair_attempted = False
            if _fix_result_has_invalid_code_fields(result, finding, path):
                repair_attempted = True
                repair_prompt = _build_fix_repair_prompt(finding, path, line, line_text, result, config)
                hardened.write_debug_text_artifact_safely(
                    config,
                    f"prompts/fix-synthesis/{index:02d}-{artifact_id}-repair.txt",
                    repair_prompt,
                )
                try:
                    repaired, repair_model, repair_tier = hardened.openrouter_review(repair_prompt, schema, config, reporter=None)
                    result = repaired
                    model_used = f"{model_used}; repair={repair_model}"
                    service_tier = repair_tier or service_tier
                except Exception as exc:
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/fix-synthesis/{index:02d}-{artifact_id}-repair-error.json",
                        {"path": path, "line": line, "error": str(exc)[:500]},
                    )
            if callable(harden_dynamic) and _patched_dynamic_exec_scope(finding, path, line_text):
                result = harden_dynamic(result, finding, path, line_text)
            guidance = _strict_fix_guidance_from_result(result, finding, path)
            hardened.write_debug_json_artifact_safely(
                config,
                f"responses/fix-synthesis/{index:02d}-{artifact_id}.json",
                {
                    "path": path,
                    "line": line,
                    "model_used": model_used,
                    "service_tier": service_tier,
                    "repair_attempted": repair_attempted,
                    "result": result,
                    "normalized_fix_guidance": guidance,
                },
            )
            enriched = dict(finding)
            suggestion = verified_suggestion(result, file_text, line, config) if callable(verified_suggestion) else ""
            if suggestion:
                enriched["suggested_replacement"] = suggestion
            elif guidance:
                enriched["fix_guidance"] = guidance
                enriched["suggested_replacement"] = ""
            validation = _clean_user_text(str(result.get("validation", "") or "").strip())
            if validation:
                enriched["validation"] = validation
            return enriched

        globals_dict["synthesize_fix_for_finding"] = patched_synthesize_fix_for_finding

    original_terms = globals_dict.get("finding_anchor_terms")
    if callable(original_terms):

        def patched_finding_anchor_terms(finding: dict[str, Any]) -> list[str]:
            terms = set(original_terms(finding))
            kinds = _finding_anchor_kinds(finding)
            if "yaml_untrusted_checkout" in kinds:
                terms.update(("github.head_ref", "github.event.pull_request.head.ref", "github.event.pull_request.head.sha", "ref:"))
            if "yaml_shell_pipe" in kinds:
                terms.update(("curl", "wget", "bash", "sh", "|"))
            if "yaml_broad_write" in kinds:
                terms.update(("permissions:", "write-all", "contents:", "pull-requests:"))
            return sorted(terms, key=lambda term: (-len(term), term))[:28]

        globals_dict["finding_anchor_terms"] = patched_finding_anchor_terms

    original_match = globals_dict.get("finding_text_matches_sentinel")
    if callable(original_match):

        def patched_finding_text_matches_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
            if original_match(finding, sentinel):
                return True
            sentinel_kind = _sentinel_anchor_kind(sentinel)
            return bool(sentinel_kind and sentinel_kind in _finding_anchor_kinds(finding))

        globals_dict["finding_text_matches_sentinel"] = patched_finding_text_matches_sentinel

    original_score = globals_dict.get("anchor_candidate_score")
    if callable(original_score):

        def patched_anchor_candidate_score(
            finding: dict[str, Any],
            candidate: Any,
            original_line: int,
            terms: list[str],
            risk_sentinels: list[Any],
        ) -> int:
            score = int(original_score(finding, candidate, original_line, terms, risk_sentinels))
            candidate_kind = _candidate_anchor_kind(candidate)
            finding_kinds = _finding_anchor_kinds(finding)
            if candidate_kind and finding_kinds:
                if candidate_kind in finding_kinds:
                    score += 140
                elif any(kind.startswith("yaml_") for kind in finding_kinds):
                    score -= 75
            return score

        globals_dict["anchor_candidate_score"] = patched_anchor_candidate_score

    original_detect_yaml = globals_dict.get("detect_github_actions_yaml_sentinels")
    if callable(original_detect_yaml):

        def patched_detect_github_actions_yaml_sentinels(diff: str) -> list[Any]:
            sentinels = list(original_detect_yaml(diff))
            seen = {(sentinel.path, sentinel.line, sentinel.label) for sentinel in sentinels}
            for changed_line in hardened.iter_added_diff_lines(diff):
                if Path(changed_line.path).suffix.lower() not in {".yml", ".yaml"}:
                    continue
                if hardened.is_comment_only_added_line(changed_line.path, changed_line.text):
                    continue
                if not CURL_BASH_RE.search(changed_line.text):
                    continue
                label = "GitHub Actions shell-piped network installer"
                key = (changed_line.path, changed_line.line, label)
                if key in seen:
                    continue
                seen.add(key)
                sentinels.append(
                    hardened.RiskSentinel(
                        path=changed_line.path,
                        line=changed_line.line,
                        label=label,
                        detail=(
                            "network-fetched scripts are piped directly into a shell; "
                            "download, verify, and execute only pinned or checksum-verified content"
                        ),
                        text=changed_line.text,
                    )
                )
            return sentinels

        globals_dict["detect_github_actions_yaml_sentinels"] = patched_detect_github_actions_yaml_sentinels


def apply_pareto_context_module(module: Any) -> None:
    """Apply explicit runtime patches to an imported Pareto context module."""
    _patch_pareto_globals(vars(module))


def _patch_main_globals(frame_globals: dict[str, Any], script_name: str) -> None:
    if script_name == "openrouter_pr_review.py":
        _patch_base_formatter_module(sys.modules["__main__"])
    elif script_name == "openrouter_pr_review_pareto_context.py":
        _patch_pareto_globals(frame_globals)


def activate(entrypoint: str | None = None) -> None:
    script_name = Path(entrypoint or sys.argv[0] or "").name
    if script_name not in REVIEW_ENTRYPOINTS:
        return
    try:
        import openrouter_pr_review as base

        _patch_base_formatter_module(base)
    except Exception:
        pass

    def patch_on_main_call(frame: Any, event: str, arg: Any) -> Any:
        if event == "call" and frame.f_code.co_name == "main":
            current_script = Path(frame.f_code.co_filename).name
            if current_script in REVIEW_ENTRYPOINTS:
                _patch_main_globals(frame.f_globals, current_script)
                sys.setprofile(None)
        return patch_on_main_call

    sys.setprofile(patch_on_main_call)
