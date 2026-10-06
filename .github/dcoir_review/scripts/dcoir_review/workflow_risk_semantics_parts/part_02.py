def _patch_yaml_extra_sentinels(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v10_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
    owner._dcoir_required_v10_original_detect_risk_sentinels = original
    if not callable(original):
        return

    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        widened_args = list(args)
        if widened_args and isinstance(widened_args[0], int):
            widened_args[0] = None
        widened_kwargs = dict(kwargs)
        for name in ("max_anchors", "max_sentinels", "limit"):
            if name in widened_kwargs:
                widened_kwargs[name] = None
        try:
            sentinels = list(original(diff, *widened_args, **widened_kwargs))
        except TypeError:
            sentinels = list(original(diff, *args, **kwargs))
        existing = {core._sentinel_key(item) for item in sentinels}
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        for path, line, text in selection._iter_added_diff_lines(diff):
            if Path(path.lower()).suffix not in {".yml", ".yaml"}:
                continue
            comment_checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
            if callable(comment_checker) and comment_checker(path, text):
                continue
            kind = _line_kind(path, text)
            if kind not in {YAML_TOKEN_TO_PR_URL, v4.YAML_METADATA_SHELL}:
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            if kind == YAML_TOKEN_TO_PR_URL:
                label = "Workflow token forwarded to PR-controlled URL"
                detail = "A GitHub token or authorization header is sent to a URL read from pull request body text."
            else:
                label = "Workflow executes pull request metadata in a shell"
                detail = "Pull request label metadata is attacker-controlled and must not be executed by a shell."
            sentinels.append(risk_sentinel_type(path=path, line=line, label=label, detail=detail, text=text))
            existing.add(key)
        return sentinels

    owner.detect_risk_sentinels = detect_risk_sentinels


def _patch_core_semantics() -> None:
    if not hasattr(core, "_dcoir_required_v10_original_line_kind"):
        core._dcoir_required_v10_original_line_kind = core._line_kind
    if not hasattr(core, "_dcoir_required_v10_original_claimed_kinds"):
        core._dcoir_required_v10_original_claimed_kinds = core._claimed_kinds
    if not hasattr(core, "_dcoir_required_v10_original_validation_for_key"):
        core._dcoir_required_v10_original_validation_for_key = core._validation_for_key
    core._line_kind = _line_kind
    core._claimed_kinds = _claimed_kinds
    core._validation_for_key = _validation_for_key
    v9._line_kind = _line_kind
    v9._claimed_kinds = _claimed_kinds
    v9._validation_for_key = _validation_for_key


def apply_pareto_context_module(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    _patch_core_semantics()
    _patch_yaml_extra_sentinels(module, hardened)
    if hardened is not None:
        _patch_yaml_extra_sentinels(hardened)
        _patch_required_selection(module, hardened)
