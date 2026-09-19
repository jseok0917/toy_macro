@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%PY%" (
    echo [ERROR] 가상환경 없음: %PY%
    pause
    exit /b 1
)

"%PY%" -m ui.app_tk --settings
exit /b %ERRORLEVEL%
