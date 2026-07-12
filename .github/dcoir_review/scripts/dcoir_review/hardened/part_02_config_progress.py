def sanitize_github_output(text: str, config: Any, neutralize_mentions: bool = True) -> str:
    if hasattr(base, "sanitize_github_output"):
        return base.sanitize_github_output(text, config, neutralize_mentions=neutralize_mentions)
    cleaned = base.sanitize_text(text, config)
    if neutralize_mentions and hasattr(base, "neutralize_github_mentions"):
        return base.neutralize_github_mentions(cleaned)
    return cleaned


def parse_yaml_like_data(path: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    raw = Path(path).read_text(encoding="utf-8")
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            data[current_key] = [] if value == "" else base.parse_scalar(value)
            continue
        if current_key and stripped.startswith("-"):
            data.setdefault(current_key, []).append(base.parse_scalar(stripped[1:].strip()))
    return data


def list_value(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in ("", None):
        return []
    return [str(value)]


def bool_value(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "on", "1"}:
        return True
    if lowered in {"false", "no", "off", "0", "none", "null", ""}:
        return False
    return bool(value)


def optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value in ("", None):
        return None
    return int(value)


def is_free_model(model: str) -> bool:
    lowered = model.strip().lower()
    return lowered == "openrouter/free" or lowered.endswith(":free")


def ensure_free_models_are_opt_in(config: Any) -> None:
    models = [config.model, *getattr(config, "model_stack", []), *getattr(config, "fallback_models", [])]
    if any(is_free_model(model) for model in models) and not getattr(config, "smoke_test_free_model", False):
        raise RuntimeError(
            "OpenRouter free-router models are smoke-test only. Set smoke_test_free_model: true "
            "only for explicit non-governed smoke runs."
        )


def load_hardened_config(path: str) -> Any:
    config = base.load_yaml_like_config(path)
    data = parse_yaml_like_data(path)

    config.model = str(data.get("model", getattr(config, "model", "openrouter/auto")))
    model_stack = list_value(data, "model_stack")
    config.model_stack = model_stack or [config.model]
    config.fallback_models = list_value(data, "fallback_models")
    config.auto_allowed_models = list_value(data, "auto_allowed_models")
    config.auto_cost_quality_tradeoff = optional_int(data, "auto_cost_quality_tradeoff")
    config.openrouter_route = str(data.get("openrouter_route", "") or "").strip()
    config.openrouter_service_tier = str(data.get("openrouter_service_tier", "") or "").strip()
    config.openrouter_session_id_prefix = str(
        data.get("openrouter_session_id_prefix", "dcoir-review") or ""
    ).strip()
    config.smoke_test_free_model = bool_value(data, "smoke_test_free_model", False)
    config.fail_on_unanchored_findings = bool_value(data, "fail_on_unanchored_findings", True)
    config.fail_on_summary_only_problem = bool_value(data, "fail_on_summary_only_problem", True)
    config.review_quality_retry_on_rejected_output = bool_value(data, "review_quality_retry_on_rejected_output", True)
    config.risk_sentinel_quality_gate = bool_value(data, "risk_sentinel_quality_gate", True)
    config.risk_sentinel_retry_on_empty = bool_value(data, "risk_sentinel_retry_on_empty", True)
    config.risk_sentinel_max_anchors = int(data.get("risk_sentinel_max_anchors", 12))
    config.script_timeout_seconds = int(data.get("script_timeout_seconds", getattr(config, "script_timeout_seconds", 1500)))
    config.debug = bool_value(data, "debug", getattr(config, "debug", False))
    config.post_progress_comment = bool_value(data, "post_progress_comment", getattr(config, "post_progress_comment", False))

    ensure_free_models_are_opt_in(config)
    return config


def model_stack_label(config: Any) -> str:
    primary = ", ".join(getattr(config, "model_stack", [config.model]))
    fallbacks = getattr(config, "fallback_models", [])
    if fallbacks:
        return f"{primary}; native fallbacks: {', '.join(fallbacks)}"
    return primary


class SimpleProgressReporter:
    def __init__(self, gh: Any, issue_number: int, command: str, config: Any) -> None:
        self.gh = gh
        self.issue_number = issue_number
        self.command = command
        self.config = config
        self.comment_id = 0
        self.steps: list[tuple[str, str]] = []

    def start(self) -> None:
        self._record("started", "accepted operator review command and initialized progress reporting")
        if getattr(self.config, "post_progress_comment", False):
            comment = self.gh.create_issue_comment(self.issue_number, self._body("running"))
            self.comment_id = int(comment.get("id", 0))

    def update(self, stage: str, message: str) -> None:
        self._record(stage, message)
        self._update_comment(self._body("running"))

    def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
        plural = "finding" if findings_count == 1 else "findings"
        self._record("completed", f"posted GitHub review; {findings_count} inline {plural}; event={review_event}")
        self._update_comment(
            self._body(
                "completed",
                final_lines=[
                    f"- Result: GitHub review posted with `{findings_count}` inline {plural}.",
                    f"- Review event: `{review_event}`.",
                ],
            )
        )

    def fail(self, message: str) -> None:
        safe_message = sanitize_github_output(message, self.config)
        self._record("failed", safe_message[:500])
        self._update_comment(
            self._body(
                "failed",
                final_lines=[
                    "- Result: review failed before a usable PR review could be posted.",
                    "",
                    "```text",
                    safe_message[:4000],
                    "```",
                ],
            ),
            create_if_missing=True,
        )

    def _record(self, stage: str, message: str) -> None:
        safe_message = sanitize_github_output(message, self.config)
        self.steps.append((stage, safe_message))
        if hasattr(base, "emit_status"):
            base.emit_status(stage, safe_message)
        else:
            print(f"[dcoir-review] {stage}: {safe_message}", flush=True)

    def _body(self, state: str, final_lines: list[str] | None = None) -> str:
        lines = [
            base.MARKER,
            f"{base.REVIEW_DISPLAY_NAME} {state}.",
            "",
            f"- Command: `{self.command}`.",
            f"- Debug progress: `{str(getattr(self.config, 'debug', False)).lower()}`.",
            *(
                base.workflow_run_status_lines(self.config)
                if hasattr(base, "workflow_run_status_lines")
                else []
            ),
            "- Branch changes: none; this workflow only posts review output.",
            "- Gate role: internal review-assist signal before any separately approved external review request.",
        ]
        if final_lines:
            lines.extend(["", *final_lines])
        lines.extend(["", "Progress:"])
        for stage, message in self.steps[-12:]:
            public_stage = base.sanitize_public_identity(stage) if hasattr(base, "sanitize_public_identity") else stage
            lines.append(f"- `{public_stage}`: {message}")
        return base.github_safe_body("\n".join(lines), limit=12000)

    def _update_comment(self, body: str, create_if_missing: bool = False) -> None:
        if not getattr(self.config, "post_progress_comment", False):
            return
        if self.comment_id:
            self.gh.update_issue_comment(self.comment_id, body)
        elif create_if_missing:
            comment = self.gh.create_issue_comment(self.issue_number, body)
            self.comment_id = int(comment.get("id", 0))


ProgressReporter = getattr(base, "ProgressReporter", SimpleProgressReporter)


def matching_command(body: str, commands: list[str]) -> str | None:
    if hasattr(base, "matching_command"):
        return base.matching_command(body, commands)
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    for command in commands:
        if re.fullmatch(rf"{re.escape(command)}(?:\s+.*)?", first_line):
            return command
    return None


def session_id(config: Any) -> str:
    prefix = getattr(config, "openrouter_session_id_prefix", "")
    if not prefix:
        return ""
    raw = f"{prefix}:{os.environ.get('GITHUB_REPOSITORY', 'repo')}:pr-{os.environ.get('PR_NUMBER', 'unknown')}"
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw)[:256]


