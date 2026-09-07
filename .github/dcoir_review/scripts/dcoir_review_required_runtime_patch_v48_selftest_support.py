"""Shared deterministic fakes for the DCOIR Review v48 selftest."""

from __future__ import annotations

from types import SimpleNamespace


REPO = "malwaredevil/dcoir-collector"
PR_NUMBER = 457
HEAD = "a" * 40
BASE = "b" * 40
NEW_HEAD = "c" * 40
NEW_BASE = "d" * 40


class FakeClient:
    def __init__(self, token: str = "token", repo: str = REPO) -> None:
        self.token = token
        self.repo = repo
        self.head = HEAD
        self.base = BASE
        self.state = "open"
        self.fail_reads = False
        self.get_pr_calls = 0
        self.review_posts = 0
        self.on_review = None

    def get_pr(self, number: int):
        self.get_pr_calls += 1
        if self.fail_reads:
            raise RuntimeError("synthetic GitHub read failure")
        assert number == PR_NUMBER
        return {
            "number": number,
            "state": self.state,
            "head": {"sha": self.head},
            "base": {"sha": self.base},
        }

    def create_review(self, number, body, event, comments, commit_id):
        assert number == PR_NUMBER
        self.review_posts += 1
        if callable(self.on_review):
            self.on_review()
        return {"id": self.review_posts, "commit_id": commit_id}


class FakeCommentGitHub:
    def __init__(self) -> None:
        self.comments: dict[int, str] = {}
        self.next_id = 1

    def create_issue_comment(self, number: int, body: str):
        assert number == PR_NUMBER
        comment_id = self.next_id
        self.next_id += 1
        self.comments[comment_id] = body
        return {"id": comment_id}

    def update_issue_comment(self, comment_id: int, body: str):
        self.comments[comment_id] = body
        return {"id": comment_id}


class FakeReporter:
    def __init__(self, gh, issue_number, command, config) -> None:
        self.gh = gh
        self.issue_number = issue_number
        self.command = command
        self.config = config
        self.comment_id = 0
        self.steps: list[tuple[str, str]] = []
        self.generic_failures = 0

    def _record(self, stage: str, message: str) -> None:
        self.steps.append((stage, message))

    def _body(self, state: str, final_lines=None) -> str:
        lines = [f"DCOIR Review {state}."]
        if final_lines:
            lines.extend(final_lines)
        return "\n".join(lines)

    def fail(self, message: str) -> None:
        self.generic_failures += 1
        self._record("failed", message)


class FakeHardened:
    ProgressReporter = FakeReporter

    def __init__(self) -> None:
        self.paid_calls = 0
        self.on_request = None
        self.artifacts: dict[str, object] = {}

    def openrouter_request_once(self, prompt, schema, config, ignored_providers, model):
        self.paid_calls += 1
        if callable(self.on_request):
            self.on_request()
        return {"summary": "clean", "findings": []}, model, ""

    def write_debug_json_artifact_safely(self, _config, path, value) -> None:
        self.artifacts[path] = value

    def sanitize_github_output(self, text: str, _config) -> str:
        return str(text)


class FakePromptModule:
    """Model v6's deliberate direct-request exception fallback."""

    def __init__(self) -> None:
        self.direct_calls = 0
        self.on_direct_request = None

    def _request_prompt_review(self, original_prompt, prompt_kind, config, hardened, base):
        self.direct_calls += 1
        if callable(self.on_direct_request):
            self.on_direct_request()
        return {"use_original": True}, "openrouter/auto", ""

    def _review_prompt_once(self, original_prompt, config, hardened, base):
        try:
            self._request_prompt_review(original_prompt, "model-prompt", config, hardened, base)
        except Exception:
            return original_prompt
        return original_prompt


class FakeModule(SimpleNamespace):
    pass


def build_fake_module(v48):
    state = {"main_exception": None}
    hardened = FakeHardened()

    def hybrid(*_args, **_kwargs):
        raise RuntimeError("synthetic per-file coverage failure")

    def original_main():
        exc = state["main_exception"]
        if exc is not None:
            raise exc

    module = FakeModule(
        base=SimpleNamespace(GitHubClient=FakeClient),
        hardened=hardened,
        openrouter_review_with_hybrid_first_pass=hybrid,
        main=original_main,
    )
    v48.apply_pareto_context_module(module)
    return module, hardened, state


def expect_raises(error_type, callback):
    try:
        callback()
    except error_type as exc:
        return exc
    raise AssertionError(f"expected {error_type.__name__}")
