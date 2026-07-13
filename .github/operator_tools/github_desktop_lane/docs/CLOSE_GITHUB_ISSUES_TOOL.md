# DCOIR Close GitHub Issues Tool

Use this tool only after deciding that all currently open non-PR issues in the target repository should be closed.

## Environment variables

The tool reads these token environment variables and never prints token values:

1. `DCOIR_GITHUB_FG_TOKEN`
2. `DCOIR_GITHUB_CL_TOKEN`

It uses the fine-grained token first and the classic token as fallback.

## Safe run order

1. Run `Run_DCOIR_CloseGitHubIssues_DryRun.cmd`.
2. Review the log and JSON report in `DCOIR_DOWNLOADS_DIR`.
3. Only if the dry-run list is correct, run `Run_DCOIR_CloseGitHubIssues_Apply.cmd`.

## Outputs

The tool writes:

- `dcoir_close_github_issues_*.log.txt`
- `dcoir_close_github_issues_*.json`

Expected success marker:

```text
DCOIR_CLOSE_GITHUB_ISSUES_DONE
```

## Stop conditions

Stop and ask for review if:

- the dry-run issue count is unexpected;
- the token is missing;
- the repo owner/name is wrong;
- the apply run reports any errors.
