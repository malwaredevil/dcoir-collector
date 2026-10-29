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
        updated = f"2026-01-01T00:00:{len(phases):02d}Z"
        entries = [json.dumps({"phase": phase, "result": "success" if phase == "final-readback" else "running"},
                              sort_keys=True) for phase in phases]
        self.write(root, f"{REPORT_PATH}/progress_history.jsonl", "\n".join(entries) + "\n")
        self.write(root, f"{REPORT_PATH}/workflow_report.md",
                   "# ChatGPT workflow report\n- result: " + result + "\n- report_updated_utc: " + updated +
                   "\n\n## Phase history\n" +
                   "\n".join(f"- {phase}" for phase in phases) + "\n")
        self.write(root, f"{REPORT_PATH}/latest_progress_marker.json",
                   json.dumps({"updated_utc": updated, "phase": phases[-1], "result": result}) + "\n")
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
        self.write(self.other, f"{REPORT_PATH}/prior_tracked_summary.md", "remote summary must survive\n")
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
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/prior_tracked_summary.md"),
                         "remote summary must survive\n")
        self.assertNotEqual(self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                                     "main", "--", REQUEST_PATH, cwd=self.root).stdout.strip(), REQUEST_PATH)
        # The publisher never rewrites the runner's checkout or local commit history.
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.writer).stdout.strip(), self.seed_head)

    def test_pre_staged_apply_in_paths_are_published_without_unstaged_files(self):
        # ChatGPT Apply-In stages product files before passing report paths only.
        self.write(self.writer, "seed.txt", "approved bundle change\n")
        self.git("add", "seed.txt", cwd=self.writer)
        self.write(self.writer, "unapproved-untracked.txt", "must stay local\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "approved bundle change\n")
        remote_names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                                "main", "--", "unapproved-untracked.txt", cwd=self.root).stdout
        self.assertEqual(remote_names.strip(), "")
        self.assertIn("seed.txt", self.git("diff", "--cached", "--name-only", cwd=self.writer).stdout)

    def test_pre_staged_deletion_is_published_for_apply_in(self):
        self.git("rm", "--", "seed.txt", cwd=self.writer)
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        remote_names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                                "main", "--", "seed.txt", cwd=self.root).stdout
        self.assertEqual(remote_names.strip(), "")

    def test_staged_but_subsequently_modified_file_fails_closed(self):
        self.write(self.writer, "seed.txt", "approved staged change\n")
        self.git("add", "seed.txt", cwd=self.writer)
        self.write(self.writer, "seed.txt", "unapproved edit after staging\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "original\n")

    def test_concurrent_main_change_to_pre_staged_file_fails_closed(self):
        self.write(self.writer, "seed.txt", "approved staged change\n")
        self.git("add", "seed.txt", cwd=self.writer)
        self.write(self.other, "seed.txt", "other writer change\n")
        self.publish_other("concurrent product edit")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "other writer change\n")

    def test_divergent_remote_history_fails_closed_without_data_loss(self):
        self.report(self.other, ["request-resolved", "remote-exclusive"])
        self.publish_other("remote second phase")
        self.report(self.writer, ["request-resolved", "local-exclusive"])
        result = self.push_report("local-exclusive")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("remote-exclusive", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))
        self.assertNotIn("local-exclusive", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))

    def test_newer_remote_report_and_marker_fail_closed_when_history_is_a_prefix(self):
        self.report(self.other, ["request-resolved"])
        report_path = self.other / REPORT_PATH / "workflow_report.md"
        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace(
                "2026-01-01T00:00:01Z", "2099-01-01T00:00:00Z"
            ) + "\nRemote final-readback evidence\n",
            encoding="utf-8",
        )
        self.write(self.other, f"{REPORT_PATH}/latest_progress_marker.json",
                   json.dumps({"updated_utc": "2099-01-01T00:00:00Z",
                               "phase": "final-readback", "result": "success"}) + "\n")
        self.publish_other("concurrent final readback")
        remote_report = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        remote_marker = self.remote_content(f"{REPORT_PATH}/latest_progress_marker.json")

        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report("running-harness")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), remote_report)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/latest_progress_marker.json"), remote_marker)

    def test_concurrent_summary_update_fails_closed(self):
        summary = f"{REPORT_PATH}/tracked_summary.md"
        self.git("config", "user.name", "Test Writer", cwd=self.writer)
        self.git("config", "user.email", "test@example.invalid", cwd=self.writer)
        self.write(self.writer, summary, "checkout summary\n")
        self.git("add", summary, cwd=self.writer)
        self.git("commit", "-m", "add tracked report summary", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)

        self.write(self.other, summary, "newer remote summary\n")
        self.publish_other("update tracked report summary")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(summary), "newer remote summary\n")

    def test_require_push_rejects_identical_already_published_content(self):
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.push_report("request-resolved-duplicate")
        self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)


if __name__ == "__main__":
    unittest.main()
