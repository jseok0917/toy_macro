from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from pathlib import Path

import config
from tab_utils import is_debug_chrome_running


def _get_chrome_major_version() -> int | None:
    """설치된 Chrome 메이저 버전 (예: 148)."""
    import re

    app_dirs = [
        config.CHROME_BINARY.parent if config.CHROME_BINARY.exists() else None,
        Path(r"C:\Program Files\Google\Chrome\Application"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application"),
    ]

    for app_dir in app_dirs:
        if not app_dir or not app_dir.exists():
            continue
        for child in sorted(app_dir.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            match = re.match(r"^(\d+)\.", child.name)
            if match:
                return int(match.group(1))

    return getattr(config, "CHROME_VERSION_MAIN", None)


def _create_stealth_driver(*, headless: bool, keep_open: bool) -> webdriver.Chrome:
    """undetected-chromedriver — Selenium/개발자도구 탐지 우회."""
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--lang=ko-KR")

    if headless:
        options.add_argument("--headless=new")

    config.CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print("[Chrome] undetected-chromedriver (탐지 우회 모드)", flush=True)
    print(f"[Chrome] 프로필: {config.CHROME_PROFILE_DIR}", flush=True)

    chrome_version = _get_chrome_major_version()
    if chrome_version:
        print(f"[Chrome] 버전: {chrome_version}", flush=True)

    driver = uc.Chrome(
        options=options,
        user_data_dir=str(config.CHROME_PROFILE_DIR),
        headless=headless,
        use_subprocess=True,
        version_main=chrome_version,
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
