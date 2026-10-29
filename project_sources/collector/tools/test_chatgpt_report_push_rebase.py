"""Regression for ChatGPT Exec same-request report publication across main changes.

Runs the actual PowerShell helper against a local bare Git remote on Windows CI.
No network, real GitHub repository, tokens, or workflow dispatch is involved.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
PUSH_HELPER = REPO_ROOT / ".github/scripts/Invoke-ChatGptReportPush.ps1"
REQUEST_ID = "issue528-rebase-repro"
REQUEST_PATH = f".github/chatgpt_staging/exec_requests/{REQUEST_ID}.json"
REPORT_PATH = f".github/chatgpt_staging/status_reports/chatgpt-exec/{REQUEST_ID}"


@unittest.skipUnless(shutil.which("pwsh") and shutil.which("git"), "requires Git and PowerShell 7")
class ChatGptReportPushRebaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dcoir-report-push-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin.git"
        self.seed = self.root / "seed"
        self.writer = self.root / "writer"
        self.other = self.root / "other"
        self.git("init", "--bare", "--initial-branch=main", str(self.origin), cwd=self.root)
        self.git("init", "--initial-branch=main", str(self.seed), cwd=self.root)
        self.git("config", "user.name", "Test Writer", cwd=self.seed)
        self.git("config", "user.email", "test@example.invalid", cwd=self.seed)
        self.write(self.seed, REQUEST_PATH, '{"approved":true}\n')
        self.write(self.seed, "seed.txt", "original\n")
        self.git("add", ".", cwd=self.seed)
        self.git("commit", "-m", "seed", cwd=self.seed)
        self.git("remote", "add", "origin", str(self.origin), cwd=self.seed)
        self.git("push", "-u", "origin", "main", cwd=self.seed)
        self.git("clone", str(self.origin), str(self.writer), cwd=self.root)
        self.git("clone", str(self.origin), str(self.other), cwd=self.root)
        self.git("config", "user.name", "Other Writer", cwd=self.other)
        self.git("config", "user.email", "other@example.invalid", cwd=self.other)
        self.seed_head = self.git("rev-parse", "HEAD", cwd=self.writer).stdout.strip()

    def run_cmd(self, args, *, cwd, success=True, timeout=100):
        result = subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                                env={**os.environ, "GITHUB_REPOSITORY": "example/local-test",
                                     "GITHUB_SERVER_URL": "https://github.com"})
        if success and result.returncode:
            self.fail(f"Command failed ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}")
        return result

    def git(self, *args, cwd):
        return self.run_cmd(["git", *map(str, args)], cwd=cwd)

    def write(self, root, relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def report(self, root, phases, result="running"):
        entries = [json.dumps({"phase": phase, "result": "success" if phase == "final-readback" else "running"},
                              sort_keys=True) for phase in phases]
        self.write(root, f"{REPORT_PATH}/progress_history.jsonl", "\n".join(entries) + "\n")
        self.write(root, f"{REPORT_PATH}/workflow_report.md",
                   "# ChatGPT workflow report\n- result: " + result + "\n\n## Phase history\n" +
                   "\n".join(f"- {phase}" for phase in phases) + "\n")
        self.write(root, f"{REPORT_PATH}/latest_progress_marker.json",
                   json.dumps({"phase": phases[-1], "result": result}) + "\n")
        if phases[-1] == "final-readback":
            self.write(root, f"{REPORT_PATH}/final_readback_marker.json",
                       '{"result":"success","exit_code":"0"}\n')

    def publish_other(self, message):
        self.git("add", ".", cwd=self.other)
        self.git("commit", "-m", message, cwd=self.other)
        self.git("push", "origin", "HEAD:main", cwd=self.other)

    def push_report(self, phase, *, required=True, paths=REPORT_PATH):
        args = ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(PUSH_HELPER),
                "-CommitMessage", f"Report {phase} [skip ci]", "-Paths", paths,
                "-MaxAttempts", "1"]
        if required:
            args.append("-RequirePush")
        return self.run_cmd(args, cwd=self.writer, success=False)

    def remote_content(self, relative):
        return self.git("--git-dir=" + str(self.origin), "show", "main:" + relative,
                        cwd=self.root).stdout

    def test_same_request_add_add_repro_with_advancing_main_and_final_cleanup(self):
        # Another published first heartbeat on main; our checkout still predates it.
        self.report(self.other, ["request-resolved"])
        self.publish_other("first heartbeat on main")
        self.report(self.writer, ["request-resolved", "running-harness"])
        first = self.push_report("running-harness")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("running-harness", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))
        # Main moves again between two phases, with unrelated committed changes.
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.write(self.other, "unrelated-main.txt", "main advanced\n")
        self.publish_other("unrelated advance")
        self.report(self.writer, ["request-resolved", "running-harness", "harness-finished"])
        middle = self.push_report("harness-finished")
        self.assertEqual(middle.returncode, 0, middle.stdout + middle.stderr)
        self.report(self.writer, ["request-resolved", "running-harness", "harness-finished", "final-readback"], result="success")
        (self.writer / REQUEST_PATH).unlink()
        final = self.push_report("final-readback", paths=REPORT_PATH + "|" + REQUEST_PATH)
        self.assertEqual(final.returncode, 0, final.stdout + final.stderr)
        history = [json.loads(line)["phase"] for line in
                   self.remote_content(f"{REPORT_PATH}/progress_history.jsonl").splitlines()]
        self.assertEqual(history, ["request-resolved", "running-harness", "harness-finished", "final-readback"])
        self.assertIn('"exit_code":"0"', self.remote_content(f"{REPORT_PATH}/final_readback_marker.json"))
        self.assertIn("- result: success", self.remote_content(f"{REPORT_PATH}/workflow_report.md"))
        self.assertEqual(self.remote_content("unrelated-main.txt"), "main advanced\n")
        self.assertNotEqual(self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                                     "main", "--", REQUEST_PATH, cwd=self.root).stdout.strip(), REQUEST_PATH)
        # The publisher never rewrites the runner's checkout or local commit history.
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.writer).stdout.strip(), self.seed_head)

    def test_other_staged_files_are_not_included_in_report_commit(self):
        self.write(self.writer, "seed.txt", "local unapproved code\n")
        self.git("add", "seed.txt", cwd=self.writer)
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "original\n")
        self.assertIn("seed.txt", self.git("diff", "--cached", "--name-only", cwd=self.writer).stdout)

    def test_divergent_remote_history_fails_closed_without_data_loss(self):
        self.report(self.other, ["request-resolved", "remote-exclusive"])
        self.publish_other("remote second phase")
        self.report(self.writer, ["request-resolved", "local-exclusive"])
        result = self.push_report("local-exclusive")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("remote-exclusive", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))
        self.assertNotIn("local-exclusive", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))

    def test_require_push_rejects_identical_already_published_content(self):
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.push_report("request-resolved-duplicate")
        self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)


if __name__ == "__main__":
    unittest.main()
