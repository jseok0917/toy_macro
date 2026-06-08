"""
자동등록 방지 처리 유틸.

click() 대신 Enter 키 전송 + 대기로 통과하는 패턴을 지원합니다.
"""

import time
from collections.abc import Callable

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def pause_for_user(message: str = "통과했으면 Enter...") -> None:
    """터미널에서 Enter를 누를 때까지 멈춥니다."""
    input(message)


def press_enter(
    driver: webdriver.Chrome,
    *,
    focus_selector: str | None = None,
    by: str = By.CSS_SELECTOR,
) -> None:
    """브라우저에 Enter 키를 보냅니다."""
    if focus_selector:
        element = driver.find_element(by, focus_selector)
        element.click()
        element.send_keys(Keys.ENTER)
    else:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)


def wait_until(
    driver: webdriver.Chrome,
    condition: Callable[[webdriver.Chrome], bool],
    *,
    timeout: float = 120,
    poll: float = 0.5,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition(driver):
            return True
        time.sleep(poll)
    return False


def wait_element_gone(
    driver: webdriver.Chrome,
    selector: str,
    *,
    by: str = By.CSS_SELECTOR,
    timeout: float = 120,
) -> bool:
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            EC.invisibility_of_element_located((by, selector))
        )
        return True
    except TimeoutException:
        return False


def wait_element_visible(
    driver: webdriver.Chrome,
    selector: str,
    *,
    by: str = By.CSS_SELECTOR,
    timeout: float = 120,
) -> bool:
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            EC.visibility_of_element_located((by, selector))
        )
        return True
    except TimeoutException:
        return False


def wait_url_change(driver: webdriver.Chrome, *, timeout: float = 120) -> bool:
    before = driver.current_url
    return wait_until(driver, lambda d: d.current_url != before, timeout=timeout)


def _wait_passed(
    driver: webdriver.Chrome,
    *,
    captcha_selector: str | None,
    success_selector: str | None,
    timeout: float,
) -> bool:
    if captcha_selector:
        return wait_element_gone(driver, captcha_selector, timeout=timeout)
    if success_selector:
        return wait_element_visible(driver, success_selector, timeout=timeout)
    return wait_url_change(driver, timeout=timeout)


def pass_captcha_with_enter(
    driver: webdriver.Chrome,
    *,
    wait_before_enter: float = 2.0,
    settle_seconds: float = 2.0,
    focus_selector: str | None = None,
    captcha_selector: str | None = None,
    success_selector: str | None = None,
    timeout: float = 120,
    retry: int = 1,
) -> bool:
    """
    Enter 키로 자동등록 방지 통과.

    1) wait_before_enter: 버튼/화면 뜰 때까지 대기
    2) Enter 전송 (focus_selector 있으면 해당 요소에 포커스 후 Enter)
    3) settle_seconds: Enter 후 검증·로딩 대기
    4) captcha/success 셀렉터 또는 URL 변경으로 통과 확인
    """
    if captcha_selector:
        print(f"[CAPTCHA] '{captcha_selector}' 표시 대기...", flush=True)
        if not wait_element_visible(driver, captcha_selector, timeout=timeout):
            print("[WARN] 방지 UI를 찾지 못함 — Enter 시도", flush=True)

    for attempt in range(1, retry + 2):
        if wait_before_enter > 0:
            print(f"[CAPTCHA] Enter 전 {wait_before_enter}초 대기...", flush=True)
            time.sleep(wait_before_enter)

        print(f"[CAPTCHA] Enter 전송 ({attempt}회)...", flush=True)
        press_enter(driver, focus_selector=focus_selector)

        if settle_seconds > 0:
            print(f"[CAPTCHA] 처리 대기 {settle_seconds}초...", flush=True)
            time.sleep(settle_seconds)

        if _wait_passed(
            driver,
            captcha_selector=captcha_selector,
            success_selector=success_selector,
            timeout=min(timeout, 30),
        ):
            print("[OK] 자동등록 방지 통과", flush=True)
            return True

        if attempt <= retry:
            print("[WARN] 아직 통과 안 됨 — Enter 재시도", flush=True)

    print("[WARN] 자동 Enter 실패 — 수동 처리 필요", flush=True)
    pause_for_user()
    return True


def wait_after_enter(
    driver: webdriver.Chrome,
    *,
    settle_seconds: float = 2.0,
    ready_selector: str | None = None,
    ready_timeout: float = 30,
) -> None:
    """Enter 후 추가 로딩 대기."""
    if settle_seconds > 0:
        time.sleep(settle_seconds)
    if ready_selector:
        wait_element_visible(driver, ready_selector, timeout=ready_timeout)
