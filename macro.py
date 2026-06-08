"""키이스케이프 예약 매크로 (F9로 실행)."""

import threading
import time
from datetime import date, timedelta
from typing import TYPE_CHECKING

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from keyescape_bypass import is_keyescape_url

if TYPE_CHECKING:
    from server_time import ServerClock

_lock = threading.Lock()
_running = False

_MASK_JS = """
const m = document.getElementById('mask');
return !m || m.classList.contains('hide') || m.offsetParent === null;
"""

_WAIT_TIME_LIST_JS = """
const m = document.getElementById('mask');
const maskOk = !m || m.classList.contains('hide') || m.offsetParent === null;
return maskOk && !!document.querySelector('#datepicker.timepicker .timeList');
"""


def _wait(driver: webdriver.Chrome, timeout: float | None = None) -> WebDriverWait:
    return WebDriverWait(
        driver,
        timeout or config.MACRO_WAIT_TIMEOUT,
        poll_frequency=config.MACRO_POLL_INTERVAL,
    )


def _js_click(driver: webdriver.Chrome, element) -> None:
    driver.execute_script("arguments[0].click();", element)


def _mask_clear(driver: webdriver.Chrome) -> bool:
    return bool(driver.execute_script(_MASK_JS))


def _wait_until_js(driver: webdriver.Chrome, script: str, timeout: float | None = None) -> None:
    deadline = time.monotonic() + (timeout or config.MACRO_WAIT_TIMEOUT)
    while time.monotonic() < deadline:
        if driver.execute_script(script):
            return
        time.sleep(config.MACRO_POLL_INTERVAL)
    raise TimeoutException(f"조건 대기 타임아웃 ({timeout or config.MACRO_WAIT_TIMEOUT}s)")


def _target_date_str(
    day_offset: int | None = None,
    server_clock: "ServerClock | None" = None,
) -> str:
    offset = config.MACRO_DAY_OFFSET if day_offset is None else day_offset
    base = server_clock.now().date() if server_clock else date.today()
    return (base + timedelta(days=offset)).strftime("%Y-%m-%d")


def _ensure_datepicker(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    if not driver.find_elements(By.CSS_SELECTOR, "#datepicker.timepicker"):
        return
    back_btns = driver.find_elements(By.ID, "back_btn")
    if not back_btns:
        return
    _js_click(driver, back_btns[0])
    wait.until(lambda d: _mask_clear(d) and d.find_elements(By.CSS_SELECTOR, "#datepicker.datepicker"))


def _click_date(driver: webdriver.Chrome, wait: WebDriverWait, date_str: str) -> None:
    _ensure_datepicker(driver, wait)

    selector = f".selDate.available[data-date='{date_str}']"
    try:
        date_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    except TimeoutException as exc:
        available = driver.execute_script(
            "return [...document.querySelectorAll('.selDate.available')].map(e => e.dataset.date);"
        )
        raise RuntimeError(
            f"예약 가능한 {date_str} 없음. 가능: {', '.join(available or []) or '없음'}"
        ) from exc

    _js_click(driver, date_el)
    _wait_until_js(driver, _WAIT_TIME_LIST_JS)


def _click_time(driver: webdriver.Chrome, wait: WebDriverWait, time_str: str) -> None:
    xpath = (
        "//ul[contains(@class,'timeList')]"
        "//label[.//input[contains(@class,'selThemeTimeNum') and not(@disabled)]]"
        f"//span[starts-with(normalize-space(), '{time_str}')]"
    )

    try:
        time_span = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    except TimeoutException as exc:
        slots = driver.execute_script(
            """
            return [...document.querySelectorAll('ul.timeList label')].map(l => {
                const s = l.querySelector('span');
                const i = l.querySelector('input.selThemeTimeNum');
                return s ? s.textContent + (i && i.disabled ? '(마감)' : '') : '';
            }).filter(Boolean);
            """
        )
        raise RuntimeError(
            f"{time_str} 없음/마감. 목록: {', '.join(slots or []) or '없음'}"
        ) from exc

    _js_click(driver, time_span.find_element(By.XPATH, "./ancestor::label"))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_next_step")))


def _click_next(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    _js_click(driver, wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_next_step"))))
    wait.until(lambda d: "reservation2.php" in d.current_url)


def _fill_form_batch(driver: webdriver.Chrome, name: str, mobile2: str, mobile3: str) -> None:
    driver.execute_script(
        """
        const [name, m2, m3] = [arguments[0], arguments[1], arguments[2]];
        const set = (sel, v) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('missing ' + sel);
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        set('#name_input', name);
        set("input[name='mobile2']", m2);
        set("input[name='mobile3']", m3);
        for (const n of ['agree_1', 'agree_2']) {
            const cb = document.querySelector(`input[name='${n}']`);
            if (cb && !cb.checked) cb.checked = true;
        }
        """,
        name,
        mobile2,
        mobile3,
    )


def _recaptcha_solved(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            "return typeof grecaptcha !== 'undefined' && grecaptcha.getResponse().length > 0;"
        )
    )


def _pass_recaptcha(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    from manual_wait import press_enter

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#captcha")))
    if _recaptcha_solved(driver):
        return

    frames = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
    if frames:
        driver.switch_to.frame(frames[0])
        try:
            anchor = driver.find_elements(By.ID, "recaptcha-anchor")
            if anchor:
                anchor[0].click()
        except Exception:
            pass
        finally:
            driver.switch_to.default_content()

    for attempt in range(1, config.CAPTCHA_ENTER_RETRY + 2):
        press_enter(driver)
        if _wait_recaptcha_poll(driver, timeout=5):
            return
        if attempt <= config.CAPTCHA_ENTER_RETRY:
            print(f"[Macro] reCAPTCHA 재시도 ({attempt})", flush=True)

    raise RuntimeError("reCAPTCHA 자동 통과 실패")


def _wait_recaptcha_poll(driver: webdriver.Chrome, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _recaptcha_solved(driver):
            return True
        time.sleep(config.MACRO_POLL_INTERVAL)
    return False


def _find_submit_button(driver: webdriver.Chrome):
    for el in driver.find_elements(By.CSS_SELECTOR, "button.submit"):
        if el.is_displayed():
            return el
    raise RuntimeError("예약하기 버튼 없음")


def _accept_alert_if_any(driver: webdriver.Chrome) -> str | None:
    try:
        alert = driver.switch_to.alert
        msg = alert.text
        alert.accept()
        return msg
    except NoAlertPresentException:
        return None


def _click_submit(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    _js_click(driver, wait.until(lambda d: _find_submit_button(d)))

    deadline = time.monotonic() + config.MACRO_SUBMIT_TIMEOUT
    while time.monotonic() < deadline:
        if "reservation3.php" in driver.current_url:
            print(f"[Macro] 예약 완료 → {driver.current_url}", flush=True)
            return
        alert_msg = _accept_alert_if_any(driver)
        if alert_msg:
            raise RuntimeError(f"예약 실패: {alert_msg}")
        time.sleep(config.MACRO_POLL_INTERVAL)

    raise RuntimeError(f"예약 제출 타임아웃 ({config.MACRO_SUBMIT_TIMEOUT}s)")


def _fill_reservation2(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#name_input")))
    name = config.get_reservation_name()
    mobile2, mobile3 = config.get_reservation_phone_parts()
    _fill_form_batch(driver, name, mobile2, mobile3)
    _pass_recaptcha(driver, wait)
    _click_submit(driver, wait)


def _run_reservation1(driver: webdriver.Chrome, wait: WebDriverWait, *, server_clock: "ServerClock | None") -> None:
    target_date = _target_date_str(server_clock=server_clock)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".reservationPick")))
    _click_date(driver, wait, target_date)
    _click_time(driver, wait, config.MACRO_TIME)
    _click_next(driver, wait)


def run_macro(driver: webdriver.Chrome, *, server_clock: "ServerClock | None" = None) -> None:
    global _running

    with _lock:
        if _running:
            print("[Macro] 이미 실행 중 — 무시", flush=True)
            return
        _running = True

    started = time.perf_counter()
    prev_implicit = config.IMPLICIT_WAIT
    driver.implicitly_wait(0)

    try:
        url = driver.current_url
        if not is_keyescape_url(url):
            print(f"[Macro] 키이스케이프 아님: {url}", flush=True)
            return

        on_step2 = "reservation2.php" in url
        on_step1 = "reservation1.php" in url
        if not on_step1 and not on_step2:
            print(f"[Macro] reservation1/2 아님: {url}", flush=True)
            return

        wait = _wait(driver)
        if on_step2:
            _fill_reservation2(driver, wait)
        else:
            _run_reservation1(driver, wait, server_clock=server_clock)
            _fill_reservation2(driver, wait)

        print(f"[Macro] 완료 ({time.perf_counter() - started:.2f}s)", flush=True)
    except Exception as exc:
        print(f"[Macro] 오류 ({time.perf_counter() - started:.2f}s): {exc}", flush=True)
    finally:
        driver.implicitly_wait(prev_implicit)
        _running = False
