@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PROFILE=%~dp0chrome_profile"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo.
echo [run.bat] 키이스케이프 매크로 시작...
echo   F9=매크로  ESC=종료  Enter=매크로  서버11:00자동
echo   ^(Chrome 자동 실행 + 예약 페이지 접속^)
echo.

if not exist "%PY%" (
    echo [ERROR] 가상환경 없음: %PY%
    echo.
    echo   python -m venv .venv
    echo   .venv\Scripts\pip.exe install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM 이전 매크로 Chrome/chromedriver 정리 (프로필 잠금 방지)
taskkill /F /IM chromedriver.exe /T >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object { $_.CommandLine -like '*keyscape*chrome_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

if exist "%PROFILE%\SingletonLock" del /f /q "%PROFILE%\SingletonLock" >nul 2>&1
if exist "%PROFILE%\SingletonSocket" del /f /q "%PROFILE%\SingletonSocket" >nul 2>&1
if exist "%PROFILE%\DevToolsActivePort" del /f /q "%PROFILE%\DevToolsActivePort" >nul 2>&1

"%PY%" "%~dp0main.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] 실행 실패 (exit %EXIT_CODE%^)
    echo   Chrome이 안 뜨면 chrome_profile 폴더 삭제 후 다시 run.bat
    pause
)

exit /b %EXIT_CODE%
