"""키이스케이프 예약 매크로 (F9로 실행)."""

import threading
import time
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException, UnexpectedAlertPresentException
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
return document.querySelectorAll('ul.timeList label span').length > 0;
"""

_LIST_TIME_SLOTS_JS = """
return [...document.querySelectorAll('ul.timeList label')].map(l => {
    const s = l.querySelector('span');
    const i = l.querySelector('input.selThemeTimeNum');
    if (!s) return null;
    const text = s.textContent.trim();
    const m = text.match(/^(\\d{1,2}:\\d{2})/);
    if (!m) return null;
    return { time: m[1], available: !!(i && !i.disabled) };
}).filter(Boolean);
"""


def _format_hms_ms(dt: datetime) -> str:
    """시:분:초.밀리초 (예: 11:00:00.005)."""
    return f"{dt.strftime('%H:%M:%S')}.{dt.microsecond // 1000:03d}"


def _macro_timing_snapshot(server_clock: "ServerClock | None" = None) -> tuple[datetime, datetime | None]:
    local = datetime.now().astimezone()
    server = server_clock.now() if server_clock else None
    return local, server


def _log_macro_timing(
    phase: str,
    *,
    local: datetime,
    server: datetime | None = None,
    elapsed_sec: float | None = None,
) -> None:
    parts = [f"[Macro] {phase} 로컬={local.strftime('%Y-%m-%d')} {_format_hms_ms(local)}"]
    if server is not None:
        parts.append(f"서버(KST)={server.strftime('%Y-%m-%d')} {_format_hms_ms(server)}")
    if elapsed_sec is not None:
        parts.append(f"경과={elapsed_sec:.3f}s")
    print("  ".join(parts), flush=True)


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


def _accept_alert_if_any(driver: webdriver.Chrome) -> str | None:
    try:
        alert = driver.switch_to.alert
        msg = alert.text
        alert.accept()
        return msg
    except NoAlertPresentException:
        return None


def _time_list_ready(driver: webdriver.Chrome) -> bool:
    return bool(driver.execute_script(_WAIT_TIME_LIST_JS))


def _retry_date_click(
    driver: webdriver.Chrome,
    selector: str,
    attempt: int,
    *,
    reason: str,
) -> None:
    print(
        f"[Macro] 재시도 ({attempt}/{config.MACRO_ALERT_RETRY_MAX}): {reason}",
        flush=True,
    )
    time.sleep(config.MACRO_ALERT_RETRY_DELAY)
    try:
        date_el = driver.find_element(By.CSS_SELECTOR, selector)
        _js_click(driver, date_el)
    except Exception:
        pass


def _wait_time_list_after_date(
    driver: webdriver.Chrome,
    date_str: str,
    selector: str,
) -> None:
    """날짜 클릭 후 시간 목록 AJAX 응답 대기. 타임아웃/alert 시에만 날짜 재클릭."""
    attempts = 0
    last_alert: str | None = None

    while True:
        deadline = time.monotonic() + config.MACRO_TIME_LIST_WAIT_TIMEOUT
        got_alert = False

        while time.monotonic() < deadline:
            alert_msg = _accept_alert_if_any(driver)
            if alert_msg:
                last_alert = alert_msg
                got_alert = True
                break

            try:
                if _time_list_ready(driver):
                    return
            except UnexpectedAlertPresentException:
                last_alert = _accept_alert_if_any(driver) or "(alert)"
                got_alert = True
                break

            time.sleep(config.MACRO_POLL_INTERVAL)

        if attempts >= config.MACRO_ALERT_RETRY_MAX:
            detail = last_alert or "시간 목록 응답 없음"
            raise RuntimeError(
                f"시간 목록 대기 실패 ({config.MACRO_ALERT_RETRY_MAX}회) "
                f"date={date_str} 마지막={detail!r}"
            )

        attempts += 1
        if got_alert:
            reason = last_alert or "(alert)"
        else:
            reason = f"시간 목록 응답 대기 타임아웃 ({config.MACRO_TIME_LIST_WAIT_TIMEOUT}s)"
        _retry_date_click(driver, selector, attempts, reason=reason)
        last_alert = None


def _target_date_str(
    day_offset: int | None = None,
    server_clock: "ServerClock | None" = None,
) -> str:
    offset = config.MACRO_DAY_OFFSET if day_offset is None else day_offset
    base = server_clock.now().date() if server_clock else date.today()
    return (base + timedelta(days=offset)).strftime("%Y-%m-%d")


def _format_target_date_label(date_str: str) -> str:
    weekdays = "월화수목금토일"
    target = date.fromisoformat(date_str)
    return f"{target.month}월 {target.day}일 ({weekdays[target.weekday()]}요일)"


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
    _wait_time_list_after_date(driver, date_str, selector)


def _format_slot_list(slots: dict[str, bool]) -> str:
    parts = []
    for time_str in config.MACRO_TIME_SLOTS:
        norm = config.normalize_hhmm(time_str)
        if norm not in slots:
            continue
        parts.append(f"{norm}{'(마감)' if not slots[norm] else ''}")
    if parts:
        return ", ".join(parts)
    return ", ".join(f"{t}{'(마감)' if not ok else ''}" for t, ok in slots.items())


def _collect_time_slots(driver: webdriver.Chrome) -> dict[str, bool]:
    raw = driver.execute_script(_LIST_TIME_SLOTS_JS) or []
    slots: dict[str, bool] = {}
    for row in raw:
        slots[config.normalize_hhmm(row["time"])] = bool(row["available"])
    return slots


def _click_time_slot(driver: webdriver.Chrome, time_str: str) -> None:
    short_wait = WebDriverWait(
        driver,
        config.MACRO_TIME_CLICK_TIMEOUT,
        poll_frequency=config.MACRO_POLL_INTERVAL,
    )
    xpath = (
        "//ul[contains(@class,'timeList')]"
        "//label[.//input[contains(@class,'selThemeTimeNum') and not(@disabled)]]"
        f"//span[starts-with(normalize-space(), '{time_str}')]"
    )
    time_span = short_wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    _js_click(driver, time_span.find_element(By.XPATH, "./ancestor::label"))
    short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_next_step")))


def _click_time(driver: webdriver.Chrome, wait: WebDriverWait) -> str:
    candidates = config.get_macro_time_candidates()
    last_slots: dict[str, bool] = {}

    for group_attempt in range(1, config.MACRO_TIME_GROUP_RETRY_MAX + 1):
        slots = _collect_time_slots(driver)
        last_slots = slots
        any_available_in_group = False

        for time_str in candidates:
            available = slots.get(time_str)
            if available is False:
                print(f"[Macro] {time_str} 마감", flush=True)
                continue
            if available is True:
                any_available_in_group = True
            try:
                _click_time_slot(driver, time_str)
            except TimeoutException:
                print(f"[Macro] {time_str} 클릭 실패", flush=True)
                slots[time_str] = False
                continue

            if time_str != config.normalize_hhmm(config.MACRO_TIME):
                print(
                    f"[Macro] {config.MACRO_TIME} 마감/불가 → {time_str} 선택",
                    flush=True,
                )
            else:
                print(f"[Macro] {time_str} 선택", flush=True)
            return time_str

        if group_attempt < config.MACRO_TIME_GROUP_RETRY_MAX:
            reason = "예약 가능 슬롯 없음" if not any_available_in_group else "클릭 실패"
            print(
                f"[Macro] 시간대 전체 재시도 ({group_attempt}/{config.MACRO_TIME_GROUP_RETRY_MAX}): {reason}",
                flush=True,
            )
            time.sleep(config.MACRO_TIME_GROUP_RETRY_DELAY)

    raise RuntimeError(
        f"예약 가능 시간 없음 (우선 {config.MACRO_TIME}, 그룹재시도 {config.MACRO_TIME_GROUP_RETRY_MAX}회). "
        f"목록: {_format_slot_list(last_slots) or '없음'}"
    )


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
            """
            if (typeof grecaptcha !== 'undefined' && grecaptcha.getResponse().length > 0) {
                return true;
            }
            const anchor = document.querySelector('#recaptcha-anchor[aria-checked="true"]');
            if (anchor) return true;
            return !!document.querySelector('.recaptcha-checkbox-checked');
            """
        )
    )


def _has_recaptcha(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.find_elements(By.CSS_SELECTOR, "#captcha")
        or driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
    )


def _wait_recaptcha_solved(driver: webdriver.Chrome, *, context: str) -> None:
    """reCAPTCHA '로봇이 아닙니다' 체크 완료까지 대기."""
    if not _has_recaptcha(driver):
        return
    if _recaptcha_solved(driver):
        return

    print(f"[Macro] reCAPTCHA 대기 ({context}) — '로봇이 아닙니다' 체크 후 진행", flush=True)

    frames = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
    if frames:
        driver.switch_to.frame(frames[0])
        try:
            anchor = driver.find_elements(By.ID, "recaptcha-anchor")
            if anchor and anchor[0].get_attribute("aria-checked") != "true":
                anchor[0].click()
        except Exception:
            pass
        finally:
            driver.switch_to.default_content()

    deadline = time.monotonic() + config.RECAPTCHA_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if _recaptcha_solved(driver):
            print("[Macro] reCAPTCHA 통과", flush=True)
            return
        time.sleep(config.MACRO_POLL_INTERVAL)

    raise RuntimeError(
        f"reCAPTCHA 타임아웃 ({config.RECAPTCHA_WAIT_TIMEOUT}s) — 체크 완료 후 다시 실행"
    )


def _pass_recaptcha(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    if _has_recaptcha(driver):
        wait.until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "#captcha")
            or d.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
        )
    _wait_recaptcha_solved(driver, context="예약하기 전")


def _find_submit_button(driver: webdriver.Chrome):
    for el in driver.find_elements(By.CSS_SELECTOR, "button.submit"):
        if el.is_displayed():
            return el
    raise RuntimeError("예약하기 버튼 없음")


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


def _refresh_reservation1(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    print("[Macro] 새로고침", flush=True)
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".reservationPick")))


def _run_reservation1(driver: webdriver.Chrome, wait: WebDriverWait, *, server_clock: "ServerClock | None") -> None:
    target_date = _target_date_str(server_clock=server_clock)
    print(
        f"[Macro] 예약 날짜 SYSDATE+{config.MACRO_DAY_OFFSET} = {target_date} "
        f"({_format_target_date_label(target_date)})",
        flush=True,
    )
    print(f"[Macro] 예약 시간 = {config.MACRO_TIME} (마감 시 이후 슬롯 자동)", flush=True)
    # _refresh_reservation1(driver, wait)
    _click_date(driver, wait, target_date)
    slots = _collect_time_slots(driver)
    print(f"[Macro] 시간 목록 확인 ({len(slots)}개)", flush=True)
    _click_time(driver, wait)
    _wait_recaptcha_solved(driver, context="NEXT 전")
    _click_next(driver, wait)


def run_macro(driver: webdriver.Chrome, *, server_clock: "ServerClock | None" = None) -> None:
    global _running

    with _lock:
        if _running:
            print("[Macro] 이미 실행 중 — 무시", flush=True)
            return
        _running = True

    started = time.perf_counter()
    start_local, start_server = _macro_timing_snapshot(server_clock)
    _log_macro_timing("시작", local=start_local, server=start_server)
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

        end_local, end_server = _macro_timing_snapshot(server_clock)
        _log_macro_timing(
            "완료",
            local=end_local,
            server=end_server,
            elapsed_sec=time.perf_counter() - started,
        )
    except Exception as exc:
        end_local, end_server = _macro_timing_snapshot(server_clock)
        _log_macro_timing(
            "오류",
            local=end_local,
            server=end_server,
            elapsed_sec=time.perf_counter() - started,
        )
        print(f"[Macro] 오류 내용: {exc}", flush=True)
    finally:
        driver.implicitly_wait(prev_implicit)
        _running = False
