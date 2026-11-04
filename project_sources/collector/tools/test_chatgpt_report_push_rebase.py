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
        self.git("config", "user.name", "Test Writer", cwd=self.writer)
        self.git("config", "user.email", "writer@example.invalid", cwd=self.writer)
        self.git("config", "user.name", "Other Writer", cwd=self.other)
        self.git("config", "user.email", "other@example.invalid", cwd=self.other)
        self.seed_head = self.git("rev-parse", "HEAD", cwd=self.writer).stdout.strip()

    def run_cmd(self, args, *, cwd, success=True, timeout=100, extra_env=None):
        env = {**os.environ, "GITHUB_REPOSITORY": "example/local-test",
               "GITHUB_SERVER_URL": "https://github.com"}
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                                env=env)
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

    def push_report(self, phase, *, required=True, paths=REPORT_PATH, job_name=None):
        args = ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(PUSH_HELPER),
                "-CommitMessage", f"Report {phase} [skip ci]", "-Paths", paths,
                "-MaxAttempts", "1"]
        if required:
            args.append("-RequirePush")
        env = {"GITHUB_JOB": job_name} if job_name is not None else None
        return self.run_cmd(args, cwd=self.writer, success=False, extra_env=env)

    def push_report_from_caller(self, phase, *, paths=REPORT_PATH):
        def ps_quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        caller = self.root / "report-push-caller.ps1"
        caller.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            f"& {ps_quote(PUSH_HELPER)} "
            f"-CommitMessage {ps_quote(f'Report {phase} [skip ci]')} "
            f"-Paths {ps_quote(paths)} -MaxAttempts 1 -RequirePush\n"
            "Write-Output 'caller continued'\n",
            encoding="utf-8",
        )
        return self.run_cmd(["pwsh", "-NoProfile", "-NonInteractive", "-File", str(caller)],
                            cwd=self.writer, success=False)

    def remote_content(self, relative):
        return self.git("--git-dir=" + str(self.origin), "show", "main:" + relative,
                        cwd=self.root).stdout

    def test_same_request_add_add_repro_with_advancing_main_and_final_cleanup(self):
        # The same runner first publishes a report, recording the exact remote version.
        self.report(self.writer, ["request-resolved"])
        initial = self.push_report("request-resolved")
        self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.write(self.other, f"{REPORT_PATH}/prior_tracked_summary.md", "remote summary must survive\n")
        self.publish_other("remote-only summary between phases")
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

    def test_other_runner_job_cannot_inherit_observation_for_same_request(self):
        self.report(self.writer, ["request-resolved"])
        initial = self.push_report("request-resolved", job_name="first-job")
        self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
        prior = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])
        another_job = self.push_report("running-harness", job_name="different-job")
        self.assertNotEqual(another_job.returncode, 0, another_job.stdout + another_job.stderr)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), prior)

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

    def test_recreated_staged_deletion_is_rejected_without_publishing_worktree(self):
        self.git("rm", "--", "seed.txt", cwd=self.writer)
        self.write(self.writer, "seed.txt", "unapproved recreated content\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "original\n")
        self.assertIn("seed.txt", self.git("diff", "--cached", "--name-only", cwd=self.writer).stdout)

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

    def test_unobserved_remote_report_fails_closed_even_with_prefix_history(self):
        self.report(self.other, ["request-resolved"])
        self.publish_other("first heartbeat from a different runner")
        original = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report("running-harness")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), original)

    def test_required_failure_propagates_through_call_operator(self):
        self.report(self.other, ["request-resolved"])
        self.publish_other("first heartbeat from a different runner")
        original = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])

        result = self.push_report_from_caller("running-harness")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), original)

    def test_later_local_timestamp_cannot_discard_unseen_remote_appendix(self):
        self.report(self.other, ["request-resolved"])
        remote_path = self.other / REPORT_PATH / "workflow_report.md"
        remote_path.write_text(
            remote_path.read_text(encoding="utf-8") + "\nRemote-only final-readback appendix\n",
            encoding="utf-8",
        )
        self.publish_other("earlier remote appendix")
        original = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report("running-harness")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), original)
        self.assertIn("Remote-only final-readback appendix", original)

    def test_concurrent_tracked_apply_report_does_not_overwrite_newer_remote(self):
        shared = ".github/chatgpt_staging/apply_reports/shared.md"
        self.write(self.writer, shared, "tracked checkout report\n")
        self.git("add", shared, cwd=self.writer)
        self.git("commit", "-m", "seed shared tracked report", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.write(self.other, shared, "newer remote apply report\n")
        self.publish_other("remote updated shared apply report")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved",
                                  paths=REPORT_PATH + "|.github/chatgpt_staging/apply_reports")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(shared), "newer remote apply report\n")

    def test_concurrent_tracked_payload_cleanup_is_rejected(self):
        updated = '{"approved":true,"newer_remote_payload":true}\n'
        self.write(self.other, REQUEST_PATH, updated)
        self.publish_other("concurrent tracked payload update")
        (self.writer / REQUEST_PATH).unlink()
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("cleanup", paths=REPORT_PATH + "|" + REQUEST_PATH)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(REQUEST_PATH), updated)

    def test_remote_tracked_deletion_cannot_be_resurrected_by_stale_directory(self):
        shared = ".github/chatgpt_staging/apply_reports/removed.md"
        self.write(self.writer, shared, "old tracked shared file\n")
        self.git("add", shared, cwd=self.writer)
        self.git("commit", "-m", "seed tracked shared file", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.git("rm", "--", shared, cwd=self.other)
        self.publish_other("remove shared file on main")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved",
                                  paths=REPORT_PATH + "|.github/chatgpt_staging/apply_reports")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        remote_names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                                "main", "--", shared, cwd=self.root).stdout
        self.assertEqual(remote_names.strip(), "")

    def test_remote_only_shared_report_is_preserved_during_safe_publication(self):
        shared_remote = ".github/chatgpt_staging/apply_reports/remote-only.md"
        shared_local = ".github/chatgpt_staging/apply_reports/new-local.md"
        self.write(self.other, shared_remote, "remote only evidence\n")
        self.publish_other("concurrent unrelated addition inside shared directory")
        self.write(self.writer, shared_local, "local apply report\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved",
                                  paths=REPORT_PATH + "|.github/chatgpt_staging/apply_reports")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(shared_remote), "remote only evidence\n")
        self.assertEqual(self.remote_content(shared_local), "local apply report\n")

    def test_nonconflicting_remote_unrelated_edit_and_local_apply_report_pass(self):
        shared_local = ".github/chatgpt_staging/apply_reports/local.md"
        self.write(self.other, "remote-unrelated.txt", "untouched remote advance\n")
        self.publish_other("unrelated main advance")
        self.write(self.writer, shared_local, "local new report\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report("request-resolved",
                                  paths=REPORT_PATH + "|.github/chatgpt_staging/apply_reports")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_content(shared_local), "local new report\n")
        self.assertEqual(self.remote_content("remote-unrelated.txt"), "untouched remote advance\n")

    def test_remote_deletion_of_checkout_tracked_history_fails_closed(self):
        history = f"{REPORT_PATH}/progress_history.jsonl"
        self.report(self.writer, ["request-resolved"])
        self.git("add", REPORT_PATH, cwd=self.writer)
        self.git("commit", "-m", "seed checkout-tracked progress history", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.git("rm", "--", history, cwd=self.other)
        self.publish_other("other runner removed tracked history")
        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report_from_caller("running-harness")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertIn("deleted on main", result.stdout + result.stderr)
        paths = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                         "main", "--", history, cwd=self.root).stdout
        self.assertEqual(paths.strip(), "")

    def test_remote_deletion_of_runner_published_history_fails_closed(self):
        history = f"{REPORT_PATH}/progress_history.jsonl"
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.git("rm", "--", history, cwd=self.other)
        self.publish_other("delete previously published progress history")
        remote_report = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report_from_caller("running-harness")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertIn("deleted on main", result.stdout + result.stderr)
        paths = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                         "main", "--", history, cwd=self.root).stdout
        self.assertEqual(paths.strip(), "")
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), remote_report)

    def test_required_recreated_staged_deletion_stops_call_operator(self):
        self.git("rm", "--", "seed.txt", cwd=self.writer)
        self.write(self.writer, "seed.txt", "unapproved reconstructed content\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report_from_caller("recreated-delete")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "original\n")

    def test_required_unstaged_index_mismatch_stops_call_operator(self):
        self.write(self.writer, "seed.txt", "approved staged content\n")
        self.git("add", "seed.txt", cwd=self.writer)
        self.write(self.writer, "seed.txt", "unstaged conflicting content\n")
        self.report(self.writer, ["request-resolved"])
        result = self.push_report_from_caller("index-mismatch")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertEqual(self.remote_content("seed.txt"), "original\n")

    def test_required_report_path_overlap_stops_call_operator(self):
        self.report(self.writer, ["request-resolved"])
        self.git("add", f"{REPORT_PATH}/workflow_report.md", cwd=self.writer)
        result = self.push_report_from_caller("overlapping-report-path")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertNotIn("workflow_report.md", self.git("--git-dir=" + str(self.origin),
                         "ls-tree", "-r", "--name-only", "main", "--", REPORT_PATH,
                         cwd=self.root).stdout)

    def test_required_invalid_report_roots_stop_call_operator(self):
        second = ".github/chatgpt_staging/status_reports/chatgpt-exec/other-request"
        self.report(self.writer, ["request-resolved"])
        self.write(self.writer, f"{second}/workflow_report.md", "# other request\n")
        result = self.push_report_from_caller("two-report-roots", paths=REPORT_PATH + "|" + second)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertIn("exactly one request-scoped report root", result.stdout + result.stderr)

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

    def test_deleted_runner_published_nonhistory_report_fails_closed(self):
        marker = f"{REPORT_PATH}/latest_progress_marker.json"
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.git("rm", "--", marker, cwd=self.other)
        self.publish_other("delete previously published nonhistory marker")
        old_report = self.remote_content(f"{REPORT_PATH}/workflow_report.md")
        self.report(self.writer, ["request-resolved", "running-harness"])
        result = self.push_report_from_caller("after-marker-deletion")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertIn("Previously published report was deleted on main", result.stdout + result.stderr)
        names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                         "main", "--", marker, cwd=self.root).stdout
        self.assertEqual(names.strip(), "")
        self.assertEqual(self.remote_content(f"{REPORT_PATH}/workflow_report.md"), old_report)

    def test_deleted_runner_published_marker_stays_deleted_if_local_also_absent(self):
        marker = f"{REPORT_PATH}/latest_progress_marker.json"
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        self.git("rm", "--", marker, cwd=self.other)
        self.publish_other("remove published marker")
        self.report(self.writer, ["request-resolved", "running-harness"])
        (self.writer / marker).unlink()
        result = self.push_report("running-harness-without-marker")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                         "main", "--", marker, cwd=self.root).stdout
        self.assertEqual(names.strip(), "")
        self.assertIn("running-harness", self.remote_content(f"{REPORT_PATH}/progress_history.jsonl"))

    def test_concurrent_explicit_report_file_deletion_fails_closed(self):
        report_file = f"{REPORT_PATH}/workflow_report.md"
        self.write(self.writer, report_file, "base report\n")
        self.git("add", report_file, cwd=self.writer)
        self.git("commit", "-m", "seed checkout-tracked report", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        self.git("pull", "--ff-only", "origin", "main", cwd=self.other)
        newer = "newer remote report evidence\n"
        self.write(self.other, report_file, newer)
        self.publish_other("other writer replaced report")
        (self.writer / report_file).unlink()
        result = self.push_report_from_caller("delete-newer-report", paths=report_file)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("caller continued", result.stdout + result.stderr)
        self.assertIn("cannot be deleted", result.stdout + result.stderr)
        self.assertEqual(self.remote_content(report_file), newer)

    def test_explicit_report_file_deletion_of_unchanged_base_is_allowed(self):
        report_file = f"{REPORT_PATH}/workflow_report.md"
        self.write(self.writer, report_file, "approved checkout report\n")
        self.git("add", report_file, cwd=self.writer)
        self.git("commit", "-m", "seed checkout report", cwd=self.writer)
        self.git("push", "origin", "HEAD:main", cwd=self.writer)
        (self.writer / report_file).unlink()
        result = self.push_report("delete-unchanged-report", paths=report_file)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = self.git("--git-dir=" + str(self.origin), "ls-tree", "-r", "--name-only",
                         "main", "--", report_file, cwd=self.root).stdout
        self.assertEqual(names.strip(), "")

    def test_require_push_rejects_identical_already_published_content(self):
        self.report(self.writer, ["request-resolved"])
        first = self.push_report("request-resolved")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.push_report("request-resolved-duplicate")
        self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)


if __name__ == "__main__":
    unittest.main()
