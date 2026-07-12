#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v11 runtime patch."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v11 as v11


WORKFLOW = ".github/workflows/dcoir-review-v11-primary-kind.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v11_probe_python.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v11_probe_powershell.ps1"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v11_optional_k8s.yml"


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def required_risk_sentinels(self, sentinels):
        return [item for item in sentinels if not v11._sentinel_key(item)[2].startswith("k8s_")]

    def write_debug_json_artifact_safely(self, _config, path, data):
        self.debug[path] = data


def sentinel(path: str, line: int, text: str, label: str = "", detail: str = "") -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label=label, detail=detail)


def risk_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 6, "  actions: write"),
        sentinel(WORKFLOW, 14, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 16, "        run: curl -fsSL https://downloads.example.invalid/install.sh | bash"),
        sentinel(WORKFLOW, 18, '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"'),
        sentinel(WORKFLOW, 21, '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"'),
        sentinel(PYTHON, 12, "    return pickle.loads(raw)"),
        sentinel(PYTHON, 16, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 20, "    return subprocess.run(command_text, shell=True, check=True)"),
        sentinel(PYTHON, 24, "        archive = tarfile.open(uploaded_archive)", "Python archive extraction setup", "Archive extraction flows into extractall."),
        sentinel(PYTHON, 25, "        archive.extractall(destination)"),
        sentinel(PYTHON, 30, '    requests.post(callback, headers={"Authorization": f"Bearer {os.environ[\'DCOIR_TOKEN\']}"})'),
        sentinel(PYTHON, 34, "    Path(user_path).write_text(payload)"),
        sentinel(POWERSHELL, 9, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        sentinel(POWERSHELL, 13, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 18, "Invoke-Expression $UserCommand"),
        sentinel(POWERSHELL, 23, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        sentinel(K8S, 7, "      hostNetwork: true"),
        sentinel(K8S, 11, "        privileged: true"),
        sentinel(K8S, 12, "        allowPrivilegeEscalation: true"),
        sentinel(K8S, 18, "      hostPath:"),
    ]


def test_primary_kind_allows_contextual_mentions() -> None:
    v11._patch_core_semantics()
    expected = {(WORKFLOW, 14): {v4.YAML_UNTRUSTED_CHECKOUT}}
    explicit_finding = {
        "path": WORKFLOW,
        "line": 14,
        "title": "Checkout uses pull request head",
        "body": "This is especially risky in a pull_request_target workflow.",
        "_anchored_line_text": "          ref: ${{ github.event.pull_request.head.sha }}",
        "_risk_sentinel_key": [WORKFLOW, 14, v4.YAML_UNTRUSTED_CHECKOUT],
    }
    model_like_finding = {
        "path": WORKFLOW,
        "line": 14,
        "title": "Checkout uses pull request head",
        "body": "This is especially risky in a pull_request_target workflow.",
        "_anchored_line_text": "          ref: ${{ github.event.pull_request.head.sha }}",
    }
    assert v11._postable_key(explicit_finding) == (WORKFLOW, 14, v4.YAML_UNTRUSTED_CHECKOUT)
    assert not v11._semantic_mismatch(explicit_finding, expected)
    assert v11._postable_key(model_like_finding) == (WORKFLOW, 14, v4.YAML_UNTRUSTED_CHECKOUT)
    assert not v11._semantic_mismatch(model_like_finding, expected)


def test_context_only_does_not_satisfy_primary_kind() -> None:
    v11._patch_core_semantics()
    expected = {(WORKFLOW, 14): {v4.YAML_UNTRUSTED_CHECKOUT}}
    finding = {
        "path": WORKFLOW,
        "line": 14,
        "title": "Workflow issue",
        "body": "The body mentions github.event.pull_request.head.sha and pull_request_target, but the title and anchor do not identify the sink.",
        "_anchored_line_text": "        name: unrelated",
    }
    assert v11._semantic_mismatch(finding, expected)


def test_wrong_title_still_fails() -> None:
    v11._patch_core_semantics()
    expected = {(WORKFLOW, 18): {v4.YAML_METADATA_SHELL}}
    finding = {
        "path": WORKFLOW,
        "line": 18,
        "title": "pull_request_target grants broad trust",
        "body": "The line executes pull request label metadata.",
        "_anchored_line_text": '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"',
    }
    assert v11._semantic_mismatch(finding, expected)


def test_blank_kind_backfills() -> None:
    v11._patch_core_semantics()
    keys = {v11._sentinel_key(item) for item in risk_sentinels()}
    assert (PYTHON, 25, v11.PYTHON_ARCHIVE_EXTRACT) in keys
    assert (PYTHON, 34, v11.PYTHON_PATH_WRITE) in keys
    assert (K8S, 7, v11.K8S_HOST_NETWORK) in keys
    assert (K8S, 11, v11.K8S_PRIVILEGED_CONTAINER) in keys
    assert (K8S, 12, v11.K8S_PRIVILEGE_ESCALATION) in keys
    assert (K8S, 18, v11.K8S_HOST_PATH) in keys
    assert v11._line_kind(PYTHON, "    Path(user_path).write_bytes(payload)") == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open(user_path, "a").write(payload)') == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open(user_path, "w+b").write(payload)') == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open(user_path, "at").write(payload)') == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open(user_path, mode="x").write(payload)') == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    Path(user_path).open(mode="wb").write(payload)') == v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open("data.txt").read()') != v11.PYTHON_PATH_WRITE
    assert v11._line_kind(PYTHON, '    open("README.md", "r").read()') != v11.PYTHON_PATH_WRITE


def test_balanced_selection_posts_twelve_and_splits_overflow() -> None:
    v11._patch_core_semantics()
    hardened = FakeHardened()
    result = v11._select_required_postable(hardened, [], risk_sentinels(), Config())
    metadata = hardened.debug["metadata/required-v11-final-selection.json"]
    selected = set(metadata["selected_keys"])
    assert len(result) == 12
    assert metadata["final_invalid_selected_keys"] == []
    assert metadata["partial_overflow"] is True
    assert metadata["overflow_required_count"] > 0
    assert metadata["overflow_optional_high_risk_count"] > 0
    assert f"{WORKFLOW}:14 {v4.YAML_UNTRUSTED_CHECKOUT}" in selected
    assert f"{WORKFLOW}:21 {v11.v10.YAML_TOKEN_TO_PR_URL}" in selected
    assert any(item.endswith(f" {v9.PYTHON_PICKLE_LOAD}") for item in selected)
    assert any(item.endswith(f" {v5.PYTHON_YAML_LOAD}") for item in selected)
    assert any(item.endswith(f" {v4.PS_ACL}") for item in selected)
    assert any(item.endswith(f" {v4.PS_PROCESS_LAUNCH}") for item in selected)
    assert any(
        item["line"] == 24 and item["kind"] == v11.PYTHON_ARCHIVE_EXTRACT
        for item in metadata["duplicate_covered_sentinels"]
    )
    assert any(
        (item.endswith(f" {v11.PYTHON_PATH_WRITE}") for item in selected)
    ) or any(
        item["kind"] == v11.PYTHON_PATH_WRITE
        for item in metadata["omitted_required_sentinels"]
    )
    assert not any("optional_k8s" in item for item in selected)


def main() -> None:
    test_primary_kind_allows_contextual_mentions()
    test_context_only_does_not_satisfy_primary_kind()
    test_wrong_title_still_fails()
    test_blank_kind_backfills()
    test_balanced_selection_posts_twelve_and_splits_overflow()
    print("dcoir_review_required_runtime_patch_v11_selftest passed")


if __name__ == "__main__":
    main()
