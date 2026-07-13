

def test_validation_is_semantic_locked() -> None:
    v14 = _load_v14()
    finding = v14._integrity_finding(mixed_findings()[0], (WORKFLOW, 17, "yaml_token_to_pr_body_url"), force_template=True)
    validation = finding["validation"]
    assert "GITHUB_TOKEN" in validation
    assert "github.event.pull_request.body" in validation
    assert "| sh" not in validation
    assert "| bash" not in validation


def test_unsafe_nested_fix_guidance_is_suppressed() -> None:
    v14 = _load_v14()
    finding = v14._integrity_finding(
        {
            "path": WORKFLOW,
            "line": 5,
            "_anchored_line_text": "  contents: write",
            "_risk_sentinel_key": [WORKFLOW, 5, "yaml_broad_write"],
            "suggested_replacement": "contents: write, read",
            "fix_guidance": {
                "language": "yaml",
                "replace": "contents: write",
                "replace_code": "contents: write, read",
                "add": "permissions: write-all",
                "notes": "Reduce permissions.",
                "validation": "stale validation",
            },
        },
        (WORKFLOW, 5, "yaml_broad_write"),
        force_template=True,
    )
    guidance = finding["fix_guidance"]
    assert finding["suggested_replacement"] == ""
    assert "replace" not in guidance
    assert "replace_code" not in guidance
    assert "add" not in guidance
    assert "validation" not in guidance


def test_same_kind_replacement_guidance_is_suppressed() -> None:
    v14 = _load_v14()

    cases = [
        (
            WORKFLOW,
            19,
            "yaml_shell_pipe",
            "        run: curl -fsSL https://downloads.example.invalid/bootstrap.sh | bash",
            "run: curl https://downloads.example.invalid/bootstrap.sh | bash",
        ),
        (
            POWERSHELL,
            15,
            "ps_dynamic_exec",
            "Invoke-Expression $UserCommand",
            "Invoke-Expression $UserCommand",
        ),
        (
            PYTHON,
            12,
            "python_pickle_load",
            "    return pickle.loads(raw)",
            "return pickle.loads(raw)",
        ),
    ]
    for path, line, kind, anchored, unsafe in cases:
        finding = v14._integrity_finding(
            {
                "path": path,
                "line": line,
                "_anchored_line_text": anchored,
                "_risk_sentinel_key": [path, line, kind],
                "suggested_replacement": unsafe,
                "fix_guidance": {
                    "language": "yaml" if path.endswith((".yml", ".yaml")) else "powershell" if path.endswith(".ps1") else "python",
                    "replace_code": unsafe,
                    "add_code": unsafe,
                    "notes": "Use a safer implementation.",
                },
            },
            (path, line, kind),
            force_template=True,
        )
        guidance = finding["fix_guidance"]
        assert finding["suggested_replacement"] == ""
        assert "replace_code" not in guidance
        assert "add_code" not in guidance


def test_render_hook_replaces_wrong_validation() -> None:
    v14 = _load_v14()

    class FakeBase:
        def build_inline_comment(self, finding: dict[str, Any], model_used: str, _config: Any) -> str:
            return (
                f"### {finding.get('title')}\n\n"
                f"{finding.get('body')}\n\n"
                "**Validation:**\n"
                f"`{finding.get('validation')}`\n\n"
                f"_Reviewed with {model_used}._"
            )

    hardened = FakeHardened()
    hardened.build_review_body_with_unanchored = lambda *_args, **_kwargs: "Base review body"
    module = SimpleNamespace(base=FakeBase(), hardened=hardened)
    v14.apply_pareto_context_module(module)
    rendered = module.base.build_inline_comment(mixed_findings()[0], "openrouter/pareto", Config())
    assert "Reviewed with " not in rendered
    assert "GITHUB_TOKEN" in rendered
    assert "github.event.pull_request.body" in rendered
    assert "| sh" not in rendered
    assert "| bash" not in rendered


def test_render_hook_collapses_duplicate_validation_sections() -> None:
    v14 = _load_v14()

    class FakeBase:
        def build_inline_comment(self, finding: dict[str, Any], _model_used: str, _config: Any) -> str:
            validation = finding.get("validation")
            return (
                f"### {finding.get('title')}\n\n"
                f"{finding.get('body')}\n\n"
                "**Validation:**\n"
                f"`{validation}`\n\n"
                "**Validation expected after fix:**\n"
                f"`{validation}`"
            )

    hardened = FakeHardened()
    hardened.build_review_body_with_unanchored = lambda *_args, **_kwargs: "Base review body"
    module = SimpleNamespace(base=FakeBase(), hardened=hardened)
    v14.apply_pareto_context_module(module)
    finding = {
        "path": POWERSHELL,
        "line": 15,
        "title": "PowerShell executes caller-controlled code",
        "body": "This line executes input as PowerShell code.",
        "_anchored_line_text": "Invoke-Expression $UserCommand",
        "_risk_sentinel_key": [POWERSHELL, 15, "ps_dynamic_exec"],
    }
    rendered = module.base.build_inline_comment(finding, "openrouter/pareto", Config())
    assert rendered.lower().count("validation") == 1
    assert rendered.count("PSParser") == 1


def test_render_hook_strips_unsafe_native_suggestion() -> None:
    v14 = _load_v14()

    class FakeBase:
        def build_inline_comment(self, finding: dict[str, Any], _model_used: str, _config: Any) -> str:
            return (
                f"### {finding.get('title')}\n\n"
                f"{finding.get('body')}\n\n"
                "```suggestion\n"
                "return pickle.loads(raw)\n"
                "```\n\n"
                f"**Validation:**\n`{finding.get('validation')}`"
            )

    hardened = FakeHardened()
    hardened.build_review_body_with_unanchored = lambda *_args, **_kwargs: "Base review body"
    module = SimpleNamespace(base=FakeBase(), hardened=hardened)
    v14.apply_pareto_context_module(module)
    finding = {
        "path": PYTHON,
        "line": 12,
        "title": "Python deserializes untrusted pickle data",
        "body": "Pickle can execute code.",
        "_anchored_line_text": "    return pickle.loads(raw)",
        "_risk_sentinel_key": [PYTHON, 12, "python_pickle_load"],
    }
    rendered = module.base.build_inline_comment(finding, "openrouter/pareto", Config())
    assert "```suggestion" not in rendered
    assert rendered.lower().count("validation") == 1


def main() -> None:
    test_required_family_balance_and_duplicate_coalescing()
    test_validation_is_semantic_locked()
    test_unsafe_nested_fix_guidance_is_suppressed()
    test_same_kind_replacement_guidance_is_suppressed()
    test_render_hook_replaces_wrong_validation()
    test_render_hook_collapses_duplicate_validation_sections()
    test_render_hook_strips_unsafe_native_suggestion()
    print("dcoir_review_required_runtime_patch_v14_selftest passed")


if __name__ == "__main__":
    main()
