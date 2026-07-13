@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-DcoirCloseGitHubIssues.ps1" -Apply -ConfirmCloseAll
echo.
echo Press Enter to close this window...
pause >nul
