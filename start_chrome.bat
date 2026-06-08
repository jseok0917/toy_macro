@echo off
chcp 65001 >nul
setlocal

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

set "USER_DATA=%LOCALAPPDATA%\Google\Chrome\User Data"
set "PORT=9222"

echo.
echo ========================================
echo  Chrome 디버그 모드 (기존 창 그대로 제어용)
echo ========================================
echo.
echo  ※ 일반 Chrome 바로가기로 연 창은 Selenium이 못 붙습니다.
echo  ※ 이 bat으로 Chrome을 켠 뒤, 평소처럼 사이트를 열어두세요.
echo  ※ 그 다음 run.bat --current 로 그 탭을 그대로 조작합니다.
echo.
echo  ※ 실행 전 Chrome 창을 모두 닫아주세요.
echo.

tasklist /FI "IMAGENAME eq chrome.exe" 2>nul | find /I "chrome.exe" >nul
if %ERRORLEVEL%==0 (
    echo [WARN] Chrome이 이미 실행 중입니다. 모두 종료 후 다시 실행하세요.
    pause
    exit /b 1
)

start "" "%CHROME%" ^
    --remote-debugging-port=%PORT% ^
    --user-data-dir="%USER_DATA%" ^
    --profile-directory=Default

timeout /t 2 /nobreak >nul

echo [OK] Chrome 실행됨.
echo.
echo  다음 단계:
echo    1. Chrome에서 원하는 페이지/탭 열기
echo    2. run.bat --current              ^(지금 탭 그대로^)
echo    3. run.bat --list-tabs            ^(탭 목록 확인^)
echo    4. run.bat --current --tab-url naver.com
echo.
pause
