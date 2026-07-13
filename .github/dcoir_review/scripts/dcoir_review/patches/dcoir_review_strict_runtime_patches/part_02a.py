

def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if base is not None:
        original = getattr(base, "_dcoir_strict_original_build_inline_comment", None)
        if original is None:
            original = getattr(base, "_dcoir_original_build_inline_comment", getattr(base, "build_inline_comment", None))
            base._dcoir_strict_original_build_inline_comment = original
        if callable(original):

            def strict_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
                return original(_strict_normalize_finding_for_comment(finding), model_used, config)

            base.build_inline_comment = strict_build_inline_comment
        base.guidance_value_looks_like_code = _strict_code_value_is_valid

    if hardened is not None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)

        def strict_is_required_risk_sentinel(sentinel: Any) -> bool:
            if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES:
                return True
            return bool(original_is_required(sentinel)) if callable(original_is_required) else False

        hardened.is_required_risk_sentinel = strict_is_required_risk_sentinel

        def strict_required_risk_sentinels(sentinels: list[Any]) -> list[Any]:
            return [sentinel for sentinel in sentinels if strict_is_required_risk_sentinel(sentinel)]

        hardened.required_risk_sentinels = strict_required_risk_sentinels

        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)

        def strict_finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
            sentinel_kind = _sentinel_kind(sentinel)
            if sentinel_kind in YAML_REQUIRED_KIND_TITLES:
                try:
                    return (
                        str(finding.get("path", "") or "") == str(getattr(sentinel, "path", "") or "")
                        and int(finding.get("line", 0) or 0) == int(getattr(sentinel, "line", 0) or 0)
                        and _semantic_kind(finding) == sentinel_kind
                    )
                except (TypeError, ValueError):
                    return False
            return bool(original_covers(finding, sentinel)) if callable(original_covers) else False

        hardened.finding_covers_risk_sentinel = strict_finding_covers_risk_sentinel

        def strict_risk_sentinel_fallback_finding(sentinel: Any, config: Any) -> dict[str, Any]:
            kind = _sentinel_kind(sentinel)
            if kind in YAML_REQUIRED_KIND_TITLES:
                return {
                    "title": YAML_REQUIRED_KIND_TITLES[kind],
                    "severity": "high",
                    "confidence": 0.99,
                    "path": getattr(sentinel, "path", ""),
                    "line": getattr(sentinel, "line", 0),
                    "body": _yaml_required_fallback_body(kind, sentinel),
                    "suggested_replacement": "",
                    "validation": getattr(hardened, "primary_validation_command", lambda _config: "")(config),
                }
            fallback = getattr(hardened, "_dcoir_strict_original_risk_sentinel_fallback_finding", None)
            return fallback(sentinel, config) if callable(fallback) else {}

        if not hasattr(hardened, "_dcoir_strict_original_risk_sentinel_fallback_finding"):
            hardened._dcoir_strict_original_risk_sentinel_fallback_finding = hardened.risk_sentinel_fallback_finding
        hardened.risk_sentinel_fallback_finding = strict_risk_sentinel_fallback_finding

        original_select = getattr(hardened, "select_findings_for_inline", None)

        def strict_add_risk_sentinel_fallback_findings(
            findings: list[dict[str, Any]],
            risk_sentinels: list[Any],
            config: Any,
            unanchored_findings: list[dict[str, Any]] | None = None,
        ) -> list[dict[str, Any]]:
            uncovered: list[Any] = []
            for sentinel in strict_required_risk_sentinels(risk_sentinels):
                sentinel_kind = _sentinel_kind(sentinel)
                # Required YAML risks need inline coverage; a body-only finding cannot satisfy exact-line review UX.
                coverage_candidates = findings if sentinel_kind in YAML_REQUIRED_KIND_TITLES else [*findings, *(unanchored_findings or [])]
                if not any(strict_finding_covers_risk_sentinel(finding, sentinel) for finding in coverage_candidates):
                    uncovered.append(sentinel)
            inline_limit = int(getattr(config, "max_inline_comments", 12))
            fallback_findings = [strict_risk_sentinel_fallback_finding(sentinel, config) for sentinel in uncovered[:inline_limit]]
            fallback_findings = [finding for finding in fallback_findings if finding]
            if not fallback_findings:
                return findings
            inserted = [
                {
                    "path": str(getattr(sentinel, "path", "") or ""),
                    "line": int(getattr(sentinel, "line", 0) or 0),
                    "kind": _sentinel_kind(sentinel),
                }
                for sentinel in uncovered[: len(fallback_findings)]
            ]
            message = "; ".join(f"{item['path']}:{item['line']} {item['kind']}" for item in inserted)
            try:
                if base is not None and hasattr(base, "emit_status"):
                    base.emit_status("required-fallback-inserted", message)
            except Exception:
                pass
            try:
                if hasattr(hardened, "write_debug_json_artifact_safely"):
                    hardened.write_debug_json_artifact_safely(
                        config,
                        "metadata/strict-required-fallback-inserted.json",
                        {"inserted": inserted},
                    )
            except Exception:
                pass
            existing_budget = max(0, inline_limit - len(fallback_findings))
            required_existing = [
                finding
                for finding in findings
                if Path(str(finding.get("path", "") or "").lower()).suffix in {".py", ".ps1", ".psm1", ".psd1"}
                or _semantic_kind(finding) in YAML_REQUIRED_KIND_TITLES
            ]
            if callable(original_select):
                existing = original_select(required_existing, existing_budget)
                if len(existing) < existing_budget:
                    extras = [finding for finding in findings if finding not in existing]
                    existing = [*existing, *original_select(extras, existing_budget - len(existing))]
            else:
                existing = required_existing[:existing_budget]
            deduped: list[dict[str, Any]] = []
            seen: set[tuple[str, int, str]] = set()
            for finding in [*existing, *fallback_findings]:
                key = (str(finding.get("path", "") or ""), int(finding.get("line", 0) or 0), _semantic_kind(finding) or str(finding.get("title", "")))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(finding)
            return deduped[:inline_limit]

        hardened.add_risk_sentinel_fallback_findings = strict_add_risk_sentinel_fallback_findings

        original_enforce = getattr(hardened, "enforce_risk_sentinel_findings", None)
        review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

        if callable(original_enforce):

            def strict_enforce_risk_sentinel_findings(
                findings: list[dict[str, Any]],
                risk_sentinels: list[Any],
                config: Any,
                unanchored_findings: list[dict[str, Any]] | None = None,
            ) -> None:
                try:
                    original_enforce(findings, risk_sentinels, config, unanchored_findings)
                    return
                except Exception as exc:
                    if not isinstance(exc, review_quality_error):
                        raise
                    augmented = strict_add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
                    if augmented == findings:
                        raise
                    original_enforce(augmented, risk_sentinels, config, unanchored_findings)
                    findings[:] = augmented

            hardened.enforce_risk_sentinel_findings = strict_enforce_risk_sentinel_findings

    original_score = getattr(module, "anchor_candidate_score", None)
    if callable(original_score):

        def strict_anchor_candidate_score(
            finding: dict[str, Any],
            candidate: Any,
            original_line: int,
            terms: list[str],
            risk_sentinels: list[Any],
        ) -> int:
            score = int(original_score(finding, candidate, original_line, terms, risk_sentinels))
            finding_kind = _semantic_kind(finding)
            candidate_kind = _candidate_kind(candidate)
            if finding_kind and candidate_kind:
                if finding_kind == candidate_kind:
                    score += 180
                elif finding_kind.startswith("yaml_") and candidate_kind.startswith("yaml_"):
                    score -= 120
            return score

        module.anchor_candidate_score = strict_anchor_candidate_score

    original_dedupe = getattr(module, "finding_dedupe_key", None)
    if callable(original_dedupe):

        def strict_finding_dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
            kind = _semantic_kind(finding)
            if kind:
                path = str(finding.get("path", "") or "").strip()
                line = "" if kind == "yaml_broad_write" else str(finding.get("line", "") or "").strip()
                return (path, line, kind, "")
            return original_dedupe(finding)

        module.finding_dedupe_key = strict_finding_dedupe_key

    file_line_text = getattr(module, "file_line_text", None)
    safe_artifact_name = getattr(module, "safe_artifact_name", None)
    verified_suggestion = getattr(module, "verified_suggested_replacement", None)
    fetch_module_base = base
    if callable(file_line_text) and callable(safe_artifact_name) and hardened is not None and fetch_module_base is not None:

        def strict_synthesize_fix_for_finding(
            index: int,
            finding: dict[str, Any],
            file_text: str,
            schema: dict[str, Any],
            config: Any,
        ) -> dict[str, Any]:
            path = str(finding.get("path", "") or "").strip()
            line = int(finding.get("line", 0) or 0)
            line_text = file_line_text(file_text, line)
            if not path or not line_text:
                return finding
            prompt = _build_strict_fix_synthesis_prompt(fetch_module_base, finding, path, line, line_text, file_text, config)
            artifact_id = safe_artifact_name(f"{path}-{line}", f"fix-{index:02d}")
            hardened.write_debug_text_artifact_safely(config, f"prompts/fix-synthesis/{index:02d}-{artifact_id}.txt", prompt)
            result, model_used, service_tier = hardened.openrouter_review(prompt, STRICT_FIX_SYNTHESIS_SCHEMA, config, reporter=None)
            repair_attempted = False
            if _code_field_invalid(result, path):
                repair_attempted = True
                repair_prompt = _build_repair_prompt(fetch_module_base, finding, path, line, line_text, result, config)
                hardened.write_debug_text_artifact_safely(config, f"prompts/fix-synthesis/{index:02d}-{artifact_id}-repair.txt", repair_prompt)
                try:
                    repaired, repair_model, repair_tier = hardened.openrouter_review(
                        repair_prompt,
                        STRICT_FIX_SYNTHESIS_SCHEMA,
                        config,
                        reporter=None,
                    )
                    result = repaired
                    model_used = f"{model_used}; repair={repair_model}"
                    service_tier = repair_tier or service_tier
                except Exception as exc:
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/fix-synthesis/{index:02d}-{artifact_id}-repair-error.json",
                        {"path": path, "line": line, "error": str(exc)[:500]},
                    )
            guidance = _strict_fix_guidance(result, finding, path)
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
            enriched["_anchored_line_text"] = line_text
            suggestion = verified_suggestion(result, file_text, line, config) if callable(verified_suggestion) else ""
            if suggestion:
                enriched["suggested_replacement"] = suggestion
            elif guidance:
                enriched["fix_guidance"] = guidance
                enriched["suggested_replacement"] = ""
            validation = _clean_public_text(str(result.get("validation", "") or ""))
            if validation:
                enriched["validation"] = validation
            return enriched

        module.synthesize_fix_for_finding = strict_synthesize_fix_for_finding
