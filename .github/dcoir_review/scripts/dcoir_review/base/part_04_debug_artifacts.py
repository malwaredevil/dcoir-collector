def debug_artifact_root(config: Config) -> Path | None:
    if not getattr(config, "debug", False):
        return None
    raw_path = os.environ.get(DEBUG_ARTIFACT_DIR_ENV, "").strip() or DEBUG_ARTIFACT_DEFAULT_DIR
    root = Path(raw_path)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve(strict=False)


def debug_artifact_path(config: Config, name: str) -> Path | None:
    root = debug_artifact_root(config)
    if root is None:
        return None
    if not DEBUG_ARTIFACT_SAFE_NAME.fullmatch(name) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError(f"unsafe debug artifact name: {name}")
    path = (root / name).resolve(strict=False)
    if path != root and root not in path.parents:
        raise ValueError(f"debug artifact path escapes root: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def bounded_debug_artifact_text(text: str, max_chars: int = DEBUG_ARTIFACT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    marker = "\n\n[debug artifact truncated by DCOIR Review]\n"
    return text[: max(0, max_chars - len(marker))].rstrip() + marker


def sanitize_debug_json_value(value: Any, config: Config) -> Any:
    if isinstance(value, str):
        return sanitize_github_output(value, config)
    if isinstance(value, dict):
        return {
            sanitize_github_output(str(key), config): sanitize_debug_json_value(item, config)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_debug_json_value(item, config) for item in value]
    if isinstance(value, tuple):
        return [sanitize_debug_json_value(item, config) for item in value]
    return value


def write_debug_text_artifact(config: Config, name: str, text: str, max_chars: int = DEBUG_ARTIFACT_MAX_CHARS) -> Path | None:
    path = debug_artifact_path(config, name)
    if path is None:
        return None
    safe_text = sanitize_github_output(str(text), config)
    path.write_text(bounded_debug_artifact_text(safe_text, max_chars), encoding="utf-8")
    return path


def write_debug_json_artifact(config: Config, name: str, data: Any, max_chars: int = DEBUG_ARTIFACT_MAX_CHARS) -> Path | None:
    path = debug_artifact_path(config, name)
    if path is None:
        return None
    safe_data = sanitize_debug_json_value(data, config)
    text = json.dumps(safe_data, indent=2, sort_keys=True, default=str)
    path.write_text(bounded_debug_artifact_text(text, max_chars) + "\n", encoding="utf-8")
    return path


def sanitized_prompt_value(value: Any, config: Config) -> str:
    return sanitize_text(str(value or ""), config)


