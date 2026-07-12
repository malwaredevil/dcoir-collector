def _patch_module_synthesis(module: Any) -> None:
    original = getattr(module, "_dcoir_required_v17_original_synthesize_fix_for_finding", None)
    if original is None:
        original = getattr(module, "synthesize_fix_for_finding", None)
        if callable(original):
            module._dcoir_required_v17_original_synthesize_fix_for_finding = original
    if not callable(original):
        return

    file_line_text = getattr(module, "file_line_text", None)
    safe_artifact_name = getattr(module, "safe_artifact_name", None)
    hardened = getattr(module, "hardened", None)

    def synthesize_fix_for_finding(
        index: int,
        finding: dict[str, Any],
        file_text: str,
        schema: dict[str, Any],
        config: Any,
    ) -> dict[str, Any]:
        enriched = original(index, finding, file_text, schema, config)
        path = str(enriched.get("path") or finding.get("path") or "")
        line = _line_number(enriched.get("line") or finding.get("line"))
        claimed_line_text = _line_text_from_finding(finding) or _line_text_from_finding(enriched)
        actual_line_text = ""
        if callable(file_line_text):
            actual_line_text = file_line_text(file_text, line)
        if not actual_line_text:
            lines = file_text.splitlines()
            if 0 < line <= len(lines):
                actual_line_text = lines[line - 1]
        if claimed_line_text and actual_line_text == claimed_line_text and _line_present_at_anchor(file_text, line, claimed_line_text):
            guidance = enriched.get("fix_guidance") if isinstance(enriched.get("fix_guidance"), dict) else {}
            if _false_missing_context(guidance.get("notes", "")):
                enriched = dict(enriched)
                enriched["_anchored_line_text"] = claimed_line_text
                enriched["_dcoir_v17_false_missing_context_suppressed"] = True
                enriched["fix_guidance"] = _guidance_with_notes(enriched, DYNAMIC_EXEC_NOTES)
                if Path(path.lower()).suffix == ".py":
                    enriched["fix_guidance"]["remove"] = claimed_line_text
                enriched["suggested_replacement"] = ""
                artifact_id = (
                    safe_artifact_name(f"{path}-{line}", f"fix-{index:02d}")
                    if callable(safe_artifact_name)
                    else f"fix-{index:02d}"
                )
                writer = getattr(hardened, "write_debug_json_artifact_safely", None) if hardened is not None else None
                if callable(writer):
                    writer(
                        config,
                        f"responses/fix-synthesis-v17/{index:02d}-{artifact_id}.json",
                        {
                            "path": path,
                            "line": line,
                            "suppressed_false_missing_context": True,
                            "anchor_match": "exact_line",
                            "raw_fix_synthesis_preserved": True,
                            "normalized_fix_guidance": enriched["fix_guidance"],
                        },
                    )
        return _canonicalized_finding(enriched)

    module.synthesize_fix_for_finding = synthesize_fix_for_finding


def apply_pareto_context_module(module: Any) -> None:
    _patch_v16_selector()
    _patch_v16_rendering()
    _patch_strict_runtime()
    _patch_module_synthesis(module)
