from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import re
import shutil
import subprocess
import time
from pathlib import Path

import config
from tab_utils import is_debug_chrome_running


def _clear_stale_profile_locks(profile_dir: Path) -> None:
    """이전 Chrome 프로세스가 남긴 lock 파일 제거."""
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"):
        path = profile_dir / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass

    devtools = profile_dir / "DevToolsActivePort"
    try:
        if devtools.exists():
            devtools.unlink()
    except OSError:
        pass


def _kill_profile_chrome(profile_dir: Path) -> None:
    """이 프로필을 쓰는 Chrome/chromedriver 종료 (캐시 잠금 해제)."""
    subprocess.run(
        ["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
        capture_output=True,
        check=False,
    )
    marker = str(profile_dir).replace("'", "''")
    ps = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        check=False,
    )
    time.sleep(0.8)


def _backup_broken_profile(profile_dir: Path) -> Path | None:
    """손상된 프로필을 백업(또는 삭제)하고 새 프로필 디렉터리 준비."""
    _kill_profile_chrome(profile_dir)
    _clear_stale_profile_locks(profile_dir)

    backup: Path | None = None
    if profile_dir.exists():
        backup = profile_dir.parent / f"{profile_dir.name}.bak.{int(time.time())}"
        try:
            shutil.move(str(profile_dir), str(backup))
            print(f"[Chrome] 손상 프로필 백업: {backup.name}", flush=True)
        except OSError as exc:
            print(
                f"[Chrome] 프로필 이동 실패 — 강제 삭제 후 새 프로필 ({exc})",
                flush=True,
            )
            # Cache 등 잠긴 폴더 먼저 제거 후 전체 삭제
            for rel in (
                Path("Default") / "Cache",
                Path("Default") / "Code Cache",
                Path("Default") / "GPUCache",
                Path("ShaderCache"),
                Path("GrShaderCache"),
            ):
                shutil.rmtree(profile_dir / rel, ignore_errors=True)
            shutil.rmtree(profile_dir, ignore_errors=True)
            if profile_dir.exists():
                raise RuntimeError(
                    f"프로필이 잠겨 있습니다. Chrome을 모두 종료한 뒤 "
                    f"폴더를 삭제하세요:\n  {profile_dir}"
                ) from exc
            backup = None

    profile_dir.mkdir(parents=True, exist_ok=True)
    return backup


def _stealth_chrome_options(*, headless: bool):
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--lang=ko-KR")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    if config.CHROME_BINARY.exists():
        options.binary_location = str(config.CHROME_BINARY)

    if headless:
        options.add_argument("--headless=new")

    return options


def _launch_stealth_chrome(
    *,
    headless: bool,
    profile_dir: Path,
    chrome_version: int | None,
) -> webdriver.Chrome:
    import undetected_chromedriver as uc

    options = _stealth_chrome_options(headless=headless)
    return uc.Chrome(
        options=options,
        user_data_dir=str(profile_dir),
        headless=headless,
        use_subprocess=True,
        version_main=chrome_version,
    )


def _get_chrome_major_version() -> int | None:
    """실제 chrome.exe 메이저 버전 (예: 149).

    Application 폴더에 대기 중인 업데이트(150 등)가 있어도
    현재 실행되는 chrome.exe 버전을 우선한다.
    """
    binary = config.CHROME_BINARY
    if binary.exists():
        try:
            result = subprocess.run(
                [str(binary), "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            text = (result.stdout or result.stderr or "").strip()
            match = re.search(r"(\d+)\.\d+\.\d+\.\d+", text)
            if match:
                return int(match.group(1))
        except (OSError, subprocess.SubprocessError, TimeoutError):
            pass

        # Windows 파일 버전 리소스
        try:
            import ctypes

            size = ctypes.windll.version.GetFileVersionInfoSizeW(str(binary), None)
            if size:
                buf = ctypes.create_string_buffer(size)
                ctypes.windll.version.GetFileVersionInfoW(str(binary), 0, size, buf)
                uflen = ctypes.c_uint()
                bufptr = ctypes.c_void_p()
                if ctypes.windll.version.VerQueryValueW(
                    buf, r"\\", ctypes.byref(bufptr), ctypes.byref(uflen)
                ):
                    class VS_FIXEDFILEINFO(ctypes.Structure):
                        _fields_ = [
                            ("dwSignature", ctypes.c_uint32),
                            ("dwStrucVersion", ctypes.c_uint32),
                            ("dwFileVersionMS", ctypes.c_uint32),
                            ("dwFileVersionLS", ctypes.c_uint32),
                            ("dwProductVersionMS", ctypes.c_uint32),
                            ("dwProductVersionLS", ctypes.c_uint32),
                            ("dwFileFlagsMask", ctypes.c_uint32),
                            ("dwFileFlags", ctypes.c_uint32),
                            ("dwFileOS", ctypes.c_uint32),
                            ("dwFileType", ctypes.c_uint32),
                            ("dwFileSubtype", ctypes.c_uint32),
                            ("dwFileDateMS", ctypes.c_uint32),
                            ("dwFileDateLS", ctypes.c_uint32),
                        ]

                    info = VS_FIXEDFILEINFO.from_address(bufptr.value)
                    return int(info.dwProductVersionMS >> 16)
        except Exception:
            pass

    # 폴더명 폴백: chrome.exe와 같은 Application 아래에서만,
    # 숫자 버전 폴더 중 chrome.dll 이 있는 가장(실제 사용)을 고른다.
    app_dirs = [
        binary.parent if binary.exists() else None,
        Path(r"C:\Program Files\Google\Chrome\Application"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application"),
    ]
    candidates: list[tuple[int, Path]] = []
    for app_dir in app_dirs:
        if not app_dir or not app_dir.exists():
            continue
        for child in app_dir.iterdir():
            if not child.is_dir():
                continue
            match = re.match(r"^(\d+)\.", child.name)
            if not match:
                continue
            if (child / "chrome.dll").exists() or (child / "chrome.exe").exists():
                candidates.append((int(match.group(1)), child))
        if candidates:
            # 동일 Application 내에서는 가장 낮은(현재 활성) 쪽이 보통 맞지만,
            # chrome.exe --version 실패 시엔 최신 폴더보다 chrome.dll 존재로 이미 필터됨.
            # 실행 중인 바이너리와 맞춰 최신 폴더를 쓰지 않도록 mtime이 아닌
            # 폴더명 중 chrome.exe 상위와 함께 있는 것만 — 여러 개면 최소 메이저 선택
            # (대기 업데이트 폴더가 더 높은 번호인 경우가 많음)
            return min(v for v, _ in candidates)

    return getattr(config, "CHROME_VERSION_MAIN", None)


def _create_stealth_driver(*, headless: bool, keep_open: bool) -> webdriver.Chrome:
    """undetected-chromedriver — Selenium/개발자도구 탐지 우회."""
    profile_dir = config.CHROME_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)
    _clear_stale_profile_locks(profile_dir)

    print("[Chrome] undetected-chromedriver (탐지 우회 모드)", flush=True)
    print(f"[Chrome] 프로필: {profile_dir}", flush=True)

    chrome_version = _get_chrome_major_version()
    if chrome_version:
        print(f"[Chrome] 버전: {chrome_version}", flush=True)

    try:
        driver = _launch_stealth_chrome(
            headless=headless,
            profile_dir=profile_dir,
            chrome_version=chrome_version,
        )
    except (SessionNotCreatedException, WebDriverException) as exc:
        msg = str(exc).lower()
        profile_issue = any(
            s in msg
            for s in (
                "chrome not reachable",
                "cannot connect to chrome",
                "session not created",
                "user data directory",
                "devtoolsactiveport",
            )
        )
        if not profile_issue:
            raise
        print("[Chrome] 프로필/버전 문제로 실행 실패 - 정리 후 재시도", flush=True)
        _backup_broken_profile(profile_dir)
        # 재시도 전 버전 재감지 (대기 업데이트 폴더 오탐 방지)
        chrome_version = _get_chrome_major_version()
        if chrome_version:
            print(f"[Chrome] 재시도 버전: {chrome_version}", flush=True)
        driver = _launch_stealth_chrome(
            headless=headless,
            profile_dir=profile_dir,
            chrome_version=chrome_version,
        )

    if not headless and config.START_MAXIMIZED:
        try:
            driver.maximize_window()
        except Exception:
            pass

    return driver


def _create_standard_driver(*, headless: bool, keep_open: bool) -> webdriver.Chrome:
    options = Options()

    if config.CHROME_BINARY.exists():
        options.binary_location = str(config.CHROME_BINARY)
        print(f"[Chrome] 실행 파일: {config.CHROME_BINARY}", flush=True)

    config.CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={config.CHROME_PROFILE_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ko-KR")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if headless:
        options.add_argument("--headless=new")
    elif config.START_MAXIMIZED:
        options.add_argument("--start-maximized")

    if keep_open:
        options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(service=Service(), options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        },
    )

    return driver


def _create_attach_driver() -> webdriver.Chrome:
    if not is_debug_chrome_running():
        raise RuntimeError(
            "디버그 모드 Chrome이 실행 중이 아닙니다.\n"
            "  ※ 키이스케이프 등 '개발자도구 금지' 사이트는 attach 불가 → profile 모드 사용\n"
            "  1) Chrome 전부 종료\n"
            "  2) start_chrome.bat 실행\n"
            "  3) run.bat --current 실행"
        )

    options = Options()
    options.add_experimental_option("debuggerAddress", config.DEBUGGER_ADDRESS)
    print(f"[Chrome] 실행 중인 Chrome에 연결 ({config.DEBUGGER_ADDRESS})", flush=True)
    print("[WARN] 개발자도구 탐지 사이트에서는 이 모드가 차단될 수 있습니다.", flush=True)
    return webdriver.Chrome(service=Service(), options=options)


def create_driver(
    *,
    headless: bool | None = None,
    mode: str | None = None,
    keep_open: bool | None = None,
) -> webdriver.Chrome:
    use_headless = headless if headless is not None else config.HEADLESS
    use_mode = mode or config.CHROME_MODE
    use_keep_open = keep_open if keep_open is not None else config.KEEP_BROWSER_OPEN

    if use_headless and use_mode == "attach":
        raise ValueError("attach 모드는 headless와 함께 사용할 수 없습니다.")

    if use_mode == "attach":
        driver = _create_attach_driver()
    elif config.USE_UNDETECTED:
        driver = _create_stealth_driver(headless=use_headless, keep_open=use_keep_open)
    else:
        driver = _create_standard_driver(headless=use_headless, keep_open=use_keep_open)

    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(config.IMPLICIT_WAIT)

    print("[Chrome] 브라우저 준비 완료", flush=True)
    return driver


def create_wait(driver: webdriver.Chrome, timeout: int | None = None) -> WebDriverWait:
    return WebDriverWait(driver, timeout or config.IMPLICIT_WAIT)
