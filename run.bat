@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo [run.bat] 키이스케이프 매크로 시작...
echo   F9=매크로  ESC=종료  Enter=매크로  서버04:00자동
echo.

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe main.py %*
) else (
    python main.py %*
)

if errorlevel 1 (
    echo.
    echo [ERROR] 실행 실패 — .venv\Scripts\python.exe 로 실행 권장
    pause
)
