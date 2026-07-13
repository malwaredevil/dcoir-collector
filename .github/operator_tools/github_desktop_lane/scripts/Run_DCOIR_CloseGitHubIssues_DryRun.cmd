@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-DcoirCloseGitHubIssues.ps1"
echo.
echo Press Enter to close this window...
pause >nul
