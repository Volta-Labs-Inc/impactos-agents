@echo off
setlocal
set "DIR=%~dp0.."
set "PY=python"
where python3 >nul 2>nul && set "PY=python3"
"%PY%" "%DIR%\cli\founder_run.py" %*
exit /b %ERRORLEVEL%
