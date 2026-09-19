"""키이스케이프 예약 매크로 (F9로 실행)."""

import threading
import time
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    order = [config.normalize_hhmm(s) for s in config.MACRO_TIME_SLOTS]
    if not order:
        order = sorted(slots.keys(), key=config.hhmm_to_minutes)
    parts = []
    for time_str in order:
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


_RECAPTCHA_TOKEN_JS = """
try {
    const areas = document.querySelectorAll(
        '#g-recaptcha-response, textarea[name="g-recaptcha-response"], textarea.g-recaptcha-response'
    );
    for (const ta of areas) {
        if (ta && ta.value && ta.value.length > 0) return ta.value;
    }
    const read = (api) => {
        if (!api || typeof api.getResponse !== 'function') return '';
        try {
            const r = api.getResponse();
            if (r && r.length > 0) return r;
        } catch (e) {}
        return '';
    };
    if (typeof grecaptcha !== 'undefined') {
        let r = read(grecaptcha);
        if (r) return r;
        r = read(grecaptcha.enterprise);
        if (r) return r;
    }
} catch (e) {}
return '';
"""


def _ensure_default_content(driver: webdriver.Chrome) -> None:
    try:
        driver.switch_to.default_content()
    except Exception:
        pass


def _recaptcha_token(driver: webdriver.Chrome) -> str:
    """부모 페이지의 reCAPTCHA 응답 토큰 (없으면 '')."""
    _ensure_default_content(driver)
    try:
        return str(driver.execute_script(_RECAPTCHA_TOKEN_JS) or "")
    except Exception:
        return ""


def _recaptcha_solved(driver: webdriver.Chrome) -> bool:
    """토큰이 있을 때만 통과. (체크 UI만으로는 이미지 챌린지 미완료일 수 있음)"""
    return bool(_recaptcha_token(driver))


def _recaptcha_anchor_frames(driver: webdriver.Chrome):
    _ensure_default_content(driver)
    frames = driver.find_elements(
        By.CSS_SELECTOR,
        "iframe[src*='recaptcha'][src*='anchor'], iframe[title*='reCAPTCHA']",
    )
    if frames:
        return frames
    return [
        f
        for f in driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
        if "bframe" not in (f.get_attribute("src") or "")
    ]


def _has_recaptcha(driver: webdriver.Chrome) -> bool:
    """페이지에 reCAPTCHA 위젯이 있는지 (iframe 껍데기만 있어도 True)."""
    _ensure_default_content(driver)
    if _recaptcha_anchor_frames(driver):
        return True
    boxes = driver.find_elements(By.CSS_SELECTOR, "#captcha, .g-recaptcha")
    for box in boxes:
        try:
            if box.find_elements(By.CSS_SELECTOR, "iframe"):
                return True
            if box.is_displayed() and box.size.get("height", 0) > 10:
                return True
        except Exception:
            continue
    return False


def _recaptcha_anchor_ready(driver: webdriver.Chrome) -> bool:
    """Google iframe 안 #recaptcha-anchor 가 실제로 그려져 클릭 가능한지."""
    for frame in _recaptcha_anchor_frames(driver):
        try:
            driver.switch_to.frame(frame)
            ready = driver.execute_script(
                """
                const a = document.querySelector('#recaptcha-anchor');
                if (!a) return false;
                const r = a.getBoundingClientRect();
                return r.width > 10 && r.height > 10;
                """
            )
            if ready:
                return True
        except Exception:
            pass
        finally:
            _ensure_default_content(driver)
    return False


def _wait_recaptcha_anchor_ready(driver: webdriver.Chrome, *, timeout: float) -> bool:
    """api.js / iframe 로드 완료까지 대기. 이전이면 클릭이 허공으로 감."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _recaptcha_solved(driver):
            return True
        if _recaptcha_anchor_ready(driver):
            return True
        time.sleep(max(config.MACRO_POLL_INTERVAL, 0.05))
    return False


def _cdp_click_at(driver: webdriver.Chrome, x: float, y: float) -> None:
    """최상위 뷰포트 좌표로 CDP 마우스 클릭."""
    for typ in ("mouseMoved", "mousePressed", "mouseReleased"):
        driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {
                "type": typ,
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
                "buttons": 1 if typ == "mousePressed" else 0,
            },
        )


def _click_recaptcha_checkbox(driver: webdriver.Chrome) -> bool:
    """anchor iframe의 '로봇이 아닙니다' 체크박스 자동 클릭."""
    for frame in _recaptcha_anchor_frames(driver):
        try:
            # 화면 밖이면 CDP 좌표가 빗나감 → 중앙으로 스크롤
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                frame,
            )
            iframe_rect = driver.execute_script(
                """
                const r = arguments[0].getBoundingClientRect();
                const vv = window.visualViewport;
                return {
                    x: r.left + (vv ? vv.offsetLeft : 0),
                    y: r.top + (vv ? vv.offsetTop : 0),
                    w: r.width,
                    h: r.height,
                };
                """,
                frame,
            )
            if not iframe_rect or iframe_rect.get("w", 0) < 10:
                continue

            driver.switch_to.frame(frame)
            info = driver.execute_script(
                """
                const a = document.querySelector('#recaptcha-anchor');
                if (!a) return null;
                a.scrollIntoView({block:'center', inline:'center'});
                const r = a.getBoundingClientRect();
                const checked = a.getAttribute('aria-checked') === 'true'
                    || a.classList.contains('recaptcha-checkbox-checked');
                return {
                    checked,
                    x: r.left + r.width / 2,
                    y: r.top + r.height / 2,
                    w: r.width,
                    h: r.height,
                };
                """
            )
            if not info:
                continue
            if info.get("checked"):
                return True
            if info.get("w", 0) < 10 or info.get("h", 0) < 10:
                continue

            # 1순위: iframe 안에서 바로 클릭 (좌표 변환 불필요, 가장 확실)
            try:
                anchor = driver.find_element(By.ID, "recaptcha-anchor")
                ActionChains(driver).move_to_element(anchor).pause(0.03).click().perform()
                return True
            except Exception:
                pass

            abs_x = float(iframe_rect["x"]) + float(info["x"])
            abs_y = float(iframe_rect["y"]) + float(info["y"])
            _ensure_default_content(driver)
            try:
                _cdp_click_at(driver, abs_x, abs_y)
                return True
            except Exception:
                driver.switch_to.frame(frame)
                anchor = driver.find_element(By.ID, "recaptcha-anchor")
                driver.execute_script(
                    "arguments[0].focus(); arguments[0].click();", anchor
                )
                return True
        except Exception:
            continue
        finally:
            _ensure_default_content(driver)
    return False


def _press_recaptcha_enter(driver: webdriver.Chrome) -> None:
    """부모 페이지에 Enter — 체크 후 토큰 확정에 사용."""
    _ensure_default_content(driver)
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ENTER)
    except Exception:
        try:
            driver.execute_script(
                """
                const e = new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true});
                (document.activeElement || document.body).dispatchEvent(e);
                document.body.dispatchEvent(
                    new KeyboardEvent('keyup', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true})
                );
                """
            )
        except Exception:
            pass


def _poll_recaptcha_token(driver: webdriver.Chrome, *, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _recaptcha_solved(driver):
            return True
        time.sleep(max(config.MACRO_POLL_INTERVAL, 0.05))
    return False


def _pass_recaptcha_auto(driver: webdriver.Chrome, *, context: str) -> None:
    """reCAPTCHA 자동 통과: 체크박스 클릭 → Enter → 토큰 폴링 (수동 입력 없음)."""
    _ensure_default_content(driver)
    if not _has_recaptcha(driver):
        return
    if _recaptcha_solved(driver):
        return

    # #captcha 껍데기만 있고 iframe 안 체크박스가 아직 없으면 클릭이 허공으로 감
    ready_timeout = float(getattr(config, "CAPTCHA_TIMEOUT", 15) or 15)
    if not _wait_recaptcha_anchor_ready(driver, timeout=ready_timeout):
        raise RuntimeError(
            f"reCAPTCHA 체크박스 로드 타임아웃 ({ready_timeout}s) — ({context})"
        )
    if _recaptcha_solved(driver):
        return

    retries = max(0, int(config.CAPTCHA_ENTER_RETRY))
    attempts = retries + 1
    # 회당 대기 짧게 — 예전엔 ~3초라 재시도가 너무 느렸음
    settle = max(0.05, float(getattr(config, "CAPTCHA_SETTLE_WAIT", 0.8) or 0.8))
    wait_before = max(0.0, float(getattr(config, "CAPTCHA_WAIT_BEFORE_ENTER", 0) or 0))
    deadline = time.monotonic() + float(config.RECAPTCHA_WAIT_TIMEOUT)
    print(f"[Macro] reCAPTCHA 자동 통과 ({context}) ×{attempts}", flush=True)

    for attempt in range(1, attempts + 1):
        if time.monotonic() >= deadline:
            break

        clicked = _click_recaptcha_checkbox(driver)
        if not clicked:
            print(f"[Macro] reCAPTCHA 체크박스 없음 ({attempt}/{attempts})", flush=True)
        else:
            print(f"[Macro] reCAPTCHA 체크 ({attempt}/{attempts})", flush=True)

        if wait_before > 0:
            time.sleep(wait_before)

        _press_recaptcha_enter(driver)

        if _poll_recaptcha_token(driver, timeout=settle):
            print("[Macro] reCAPTCHA 통과", flush=True)
            return

    remain = max(0.0, deadline - time.monotonic())
    if remain > 0 and _poll_recaptcha_token(driver, timeout=remain):
        print("[Macro] reCAPTCHA 통과", flush=True)
        return

    raise RuntimeError(
        f"reCAPTCHA 자동 통과 실패 ({config.RECAPTCHA_WAIT_TIMEOUT}s) — "
        "프로필/탐지 문제일 수 있음. chrome_profile 삭제 후 재실행"
    )


def _wait_recaptcha_solved(driver: webdriver.Chrome, *, context: str) -> None:
    _pass_recaptcha_auto(driver, context=context)


def _pass_recaptcha(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    _ensure_default_content(driver)
    # 껍데기(#captcha)가 아니라 실제 anchor iframe이 뜰 때까지
    try:
        wait.until(
            lambda d: _recaptcha_solved(d)
            or bool(_recaptcha_anchor_frames(d))
            or _has_recaptcha(d)
        )
    except TimeoutException:
        pass
    _pass_recaptcha_auto(driver, context="예약하기 전")


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
    fallback = "켜짐" if config.MACRO_TIME_FALLBACK_ENABLED else "꺼짐"
    print(
        f"[Macro] 예약 시간 = {config.MACRO_TIME} (이후 슬롯 자동: {fallback})",
        flush=True,
    )
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
