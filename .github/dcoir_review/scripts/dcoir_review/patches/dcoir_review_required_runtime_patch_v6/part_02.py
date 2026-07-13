def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if base is None or hardened is None:
        return
    if not hasattr(v3, "_strip_fences"):
        v3._strip_fences = v2._strip_fences
    _patch_sanitize_text(base)
    _patch_yaml_metadata_priority()
    _patch_merge_summary(hardened)
    _patch_required_coverage_debug(hardened)
    _patch_openrouter_prompt_review(hardened, base)
