#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

status=0
explicit_scope=0
files_file="$(mktemp)"
existing_files_file="$(mktemp)"
python_files_file="$(mktemp)"
trap 'rm -f "$files_file" "$existing_files_file" "$python_files_file"' EXIT

if [ "$#" -gt 0 ]; then
  explicit_scope=1
  printf '%s\n' "$@" > "$files_file"
elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  base_ref="${CODEX_BASE_REF:-origin/main}"

  if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
    base_ref="${CODEX_BASE_FALLBACK_REF:-main}"
  fi

  if git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
    git diff --name-only --diff-filter=ACMRTUXB "$base_ref"...HEAD > "$files_file" || true
  elif git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    git diff --name-only --diff-filter=ACMRTUXB HEAD~1...HEAD > "$files_file" || true
  else
    : > "$files_file"
  fi

  git diff --cached --name-only --diff-filter=ACMRTUXB >> "$files_file" || true
  git diff --name-only --diff-filter=ACMRTUXB >> "$files_file" || true

  sort -u "$files_file" -o "$files_file"
else
  : > "$files_file"
fi

while IFS= read -r file; do
  [ -f "$file" ] && printf '%s\n' "$file"
done < "$files_file" > "$existing_files_file"

while IFS= read -r file; do
  case "$file" in
    *.py)
      [ -f "$file" ] && printf '%s\n' "$file"
      ;;
  esac
done < "$files_file" > "$python_files_file"

echo '[validate-codex-local] changed or selected files:'
sed -n '1,200p' "$files_file"

if [ ! -s "$files_file" ]; then
  echo '[validate-codex-local] no changed or selected files; nothing to validate'
  git status --short || true
  exit 0
fi

filter_secret_scan_output() {
  grep -Ev "REQUIRED_TOKEN[[:space:]]*=[[:space:]]*['\"]APPLY_[A-Z0-9_]+['\"]" \
    | grep -Ev "['\"]?[A-Z][A-Z0-9_]*(TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*['\"]?"
}

run_secret_scan() {
  if [ ! -s "$existing_files_file" ]; then
    echo '[validate-codex-local] no existing files selected for secret-pattern scan'
    return 1
  fi

  mapfile -t existing_files < "$existing_files_file"
  if [ "${#existing_files[@]}" -eq 0 ]; then
    echo '[validate-codex-local] no existing files selected for secret-pattern scan'
    return 1
  fi

  rg -n --hidden \
    -g '!.git' \
    -g '!node_modules' \
    -g '!dist' \
    -g '!build' \
    -g '!vendor' \
    -e 'github_pat_[A-Za-z0-9_]{20,}' \
    -e 'gh[pousr]_[A-Za-z0-9_]{20,}' \
    -e 'AKIA[0-9A-Z]{16}' \
    -e '-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----' \
    -e '(?i)(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_./+=-]{16,}' \
    -- "${existing_files[@]}" \
    | filter_secret_scan_output || true
}

if command -v rg >/dev/null 2>&1; then
  echo '[validate-codex-local] secret-pattern scan'
  if scan_output="$(run_secret_scan)" && [ -n "$scan_output" ]; then
    printf '%s\n' "$scan_output"
    echo '[validate-codex-local] potential secret patterns found'
    status=1
  else
    echo '[validate-codex-local] no obvious secret patterns found in selected scope'
  fi
else
  echo '[validate-codex-local] WARN: rg not available; skipping secret scan'
fi

if grep -Eq '\.sh$' "$files_file"; then
  echo '[validate-codex-local] shell checks'
  while IFS= read -r file; do
    [ -f "$file" ] || continue
    case "$file" in
      *.sh)
        if command -v shellcheck >/dev/null 2>&1; then
          shellcheck "$file" || status=1
        fi
        if command -v shfmt >/dev/null 2>&1; then
          shfmt -d "$file" || echo "[validate-codex-local] WARN: shfmt reported formatting differences for $file"
        fi
        ;;
    esac
  done < "$files_file"
fi

if grep -Eq '\.(yml|yaml)$' "$files_file"; then
  echo '[validate-codex-local] yaml checks'
  if command -v yamllint >/dev/null 2>&1; then
    while IFS= read -r file; do
      [ -f "$file" ] || continue
      case "$file" in
        *.yml | *.yaml)
          if [ -f .yamllint ] || [ -f .yamllint.yml ] || [ -f .yamllint.yaml ]; then
            yamllint "$file" || status=1
          else
            yamllint "$file" || echo "[validate-codex-local] WARN: yamllint reported style findings for $file without a repo yamllint config"
          fi
          ;;
      esac
    done < "$files_file"
  else
    echo '[validate-codex-local] WARN: yamllint not available'
  fi
fi

if [ -s "$python_files_file" ]; then
  echo '[validate-codex-local] python checks'
  mapfile -t python_files < "$python_files_file"
  if command -v ruff >/dev/null 2>&1; then
    ruff check -- "${python_files[@]}" || status=1
  else
    echo '[validate-codex-local] WARN: ruff not available'
  fi

  if command -v bandit >/dev/null 2>&1; then
    bandit -q -- "${python_files[@]}" || status=1
  else
    echo '[validate-codex-local] WARN: bandit not available'
  fi
fi

if [ "${CODEX_RUN_SEMGREP:-0}" = "1" ] && command -v semgrep >/dev/null 2>&1; then
  echo '[validate-codex-local] semgrep checks'
  if [ -f .semgrep.yml ]; then
    semgrep --config .semgrep.yml . || status=1
  else
    echo '[validate-codex-local] WARN: CODEX_RUN_SEMGREP=1 but no .semgrep.yml exists; skipping semgrep to avoid remote rule dependency'
  fi
fi

if grep -Eq '(^\.github/(actions|workflows)/|^\.github/dcoir_review/scripts/validate-codex-local\.sh$|^project_sources/collector/(powershell_|PSScriptAnalyzerSettings\.psd1|fixtures/powershell_(analysis|review_assist)/|tools/(run_powershell_|test_run_powershell_|powershell_analyzer_).*\.(py|json)|source/|harness/))' "$files_file"; then
  echo '[validate-codex-local] PowerShell review-assist report check'
  python3 project_sources/collector/tools/run_powershell_review_assist_report.py --repo-root . --no-write || status=1
fi

if grep -Eq '\.(ps1|psm1|psd1)$' "$files_file"; then
  echo '[validate-codex-local] PowerShell parser checks'
  if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowPowerShell7 -AllowEmpty || status=1
  elif command -v powershell >/dev/null 2>&1; then
    powershell_info="$(powershell -NoProfile -Command '$PSVersionTable.PSEdition + ":" + $PSVersionTable.PSVersion.Major' 2>/dev/null || true)"
    if [ "$powershell_info" = "Desktop:5" ]; then
      powershell -NoProfile -ExecutionPolicy Bypass -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowEmpty || status=1
    else
      powershell -NoProfile -ExecutionPolicy Bypass -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowPowerShell7 -AllowEmpty || status=1
    fi
  else
    echo '[validate-codex-local] WARN: no PowerShell executable available'
  fi
fi

if [ -f .github/dcoir_review/scripts/validate-codeql-security-workflow.py ]; then
  echo '[validate-codex-local] CodeQL workflow config check'
  python3 .github/dcoir_review/scripts/validate-codeql-security-workflow.py || status=1
fi

git status --short || true
exit "$status"
