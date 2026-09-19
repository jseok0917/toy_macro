import os
import re
import urllib.error
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent

# ── Chrome (실제 브라우저) ──────────────────────────────────────
# CHROME_MODE:
#   "profile" → 새 Chrome 창 (키이스케이프 등 봇 차단 사이트용, 권장)
#   "attach"  → 디버그 Chrome 연결 (개발자도구 탐지 사이트에서는 차단됨)
CHROME_MODE = "profile"

# Selenium 탐지 우회 (키이스케이프 등 필수)
USE_UNDETECTED = True

# Chrome 메이저 — 자동 감지 실패 시 수동 지정 (현재 설치: 149)
CHROME_VERSION_MAIN = 149

CHROME_BINARY = Path(
    os.environ.get(
        "CHROME_BINARY",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
)

# profile 모드: 프로젝트 전용 Chrome 프로필 (실제 Chrome과 동일하게 세션 유지)
CHROME_PROFILE_DIR = BASE_DIR / "chrome_profile"

# attach 모드: start_chrome.bat 으로 켠 Chrome 디버그 포트
DEBUGGER_ADDRESS = "127.0.0.1:9222"

HEADLESS = False              # True면 창 숨김 (자동등록 방지 시 False 필수)
START_MAXIMIZED = True
KEEP_BROWSER_OPEN = True      # 스크립트 종료 후에도 Chrome 창 유지
PAGE_LOAD_TIMEOUT = 30
IMPLICIT_WAIT = 10

# attach 모드에서 사용할 Windows 기본 Chrome 프로필 (Chrome 완전 종료 후 bat 실행)
WINDOWS_USER = os.environ.get("USERNAME", "")
SYSTEM_CHROME_USER_DATA = Path(
    os.environ.get(
        "CHROME_USER_DATA",
        rf"C:\Users\{WINDOWS_USER}\AppData\Local\Google\Chrome\User Data",
    )
)
SYSTEM_CHROME_PROFILE = "Default"

# ── reCAPTCHA 자동 통과 (체크박스 클릭 + Enter) ─────────────────
CAPTCHA_TIMEOUT = 15          # 체크박스 로드 대기(초)
RECAPTCHA_WAIT_TIMEOUT = 12   # 전체 자동 통과 제한(초)
CAPTCHA_WAIT_BEFORE_ENTER = 0.05
CAPTCHA_SETTLE_WAIT = 0.8     # 클릭 후 토큰 확인(회당)
CAPTCHA_ENTER_RETRY = 10

# CAPTCHA_FOCUS_SELECTOR = "button"
# CAPTCHA_SELECTOR = "#captcha-box"
# SUCCESS_SELECTOR = "#main-content"

# ── 예약자 정보 ─────────────────────────────────────────────────
RESERVATION_NAME = "석지명"
RESERVATION_PHONE = "2736-3607"   # 010은 페이지 고정, mobile2-mobile3


def get_reservation_name() -> str:
    name = RESERVATION_NAME.strip()
    if not name:
        raise RuntimeError("config.RESERVATION_NAME 이 비어 있습니다.")
    return name


def get_reservation_phone_parts() -> tuple[str, str]:
    """010-XXXX-XXXX 중 mobile2, mobile3 (각 4자리)."""
    raw = RESERVATION_PHONE.strip()
    if not raw:
        raise RuntimeError("config.RESERVATION_PHONE 이 비어 있습니다.")
    if "-" in raw:
        mid, last = raw.split("-", 1)
        mid, last = re.sub(r"\D", "", mid), re.sub(r"\D", "", last)
    else:
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 8:
            raise RuntimeError(
                f"RESERVATION_PHONE 형식 오류: {raw!r} (2736-3607 또는 8자리)"
            )
        mid, last = digits[:4], digits[4:]
    if len(mid) != 4 or len(last) != 4:
        raise RuntimeError(f"RESERVATION_PHONE 각段 4자리 필요: {raw!r}")
    return mid, last

# ── 예약 대상 (여기만 수정) ─────────────────────────────────────
### 투투어드벤처
ZIZUM_NUM = 23              # 지점 번호
THEME_NUM = 69              # 테마 번호
THEME_INFO_NUM = 60         # 테마 상세 번호 (theme_info_num)
### 머니머니패키지
# ZIZUM_NUM = 19              # 지점 번호
# THEME_NUM = 60              # 테마 번호
# THEME_INFO_NUM = 38         # 테마 상세 번호 (theme_info_num)

RESERVATION_BASE_URL = "https://www.keyescape.com/reservation1.php"


def build_reservation_url(
    *,
    zizum_num: int | str | None = None,
    theme_num: int | str | None = None,
    theme_info_num: int | str | None = None,
) -> str:
    """config 예약 변수로 접속 URL 생성."""
    z = zizum_num if zizum_num is not None else ZIZUM_NUM
    t = theme_num if theme_num is not None else THEME_NUM
    i = theme_info_num if theme_info_num is not None else THEME_INFO_NUM
    return (
        f"{RESERVATION_BASE_URL}"
        f"?zizum_num={z}&theme_num={t}&theme_info_num={i}"
    )


# ── 매크로 (예약 일시) ───────────────────────────────────────────
MACRO_HOTKEY = "f9"
MACRO_DAY_OFFSET = 6          # 서버 SYSDATE + N 일
MACRO_TIME = "18:55"          # 우선 예약 시간 (HH:MM)
MACRO_TIME_FALLBACK_ENABLED = True  # False면 MACRO_TIME만 시도 (마감 시 이후 슬롯 미사용)

# 테마별 시간 슬롯 — run.bat 시작 시 API(get_theme_time)로 채움
MACRO_TIME_SLOTS: list[str] = []


def normalize_hhmm(value: str) -> str:
    hour, minute = value.strip().split(":", 1)
    return f"{int(hour):02d}:{int(minute):02d}"


def hhmm_to_minutes(value: str) -> int:
    hour, minute = normalize_hhmm(value).split(":")
    return int(hour) * 60 + int(minute)


def refresh_macro_time_slots(
    *,
    date: str | None = None,
    zizum_num: int | str | None = None,
    theme_num: int | str | None = None,
    end_day: int | str = 0,
):
    """서버 SYSDATE(또는 지정일) 기준 시간 슬롯을 API에서 받아 MACRO_TIME_SLOTS 갱신."""
    from datetime import datetime

    from keyescape_api import fetch_theme_time_slots
    from server_time import KST, fetch_server_now

    global MACRO_TIME_SLOTS

    if date is None:
        try:
            date = fetch_server_now().strftime("%Y-%m-%d")
        except (OSError, RuntimeError, urllib.error.URLError):
            date = datetime.now(KST).strftime("%Y-%m-%d")

    z = zizum_num if zizum_num is not None else ZIZUM_NUM
    t = theme_num if theme_num is not None else THEME_NUM
    api_slots = fetch_theme_time_slots(
        date,
        zizum_num=z,
        theme_num=t,
        end_day=end_day,
    )
    MACRO_TIME_SLOTS = [normalize_hhmm(s.time) for s in api_slots]
    return api_slots


def get_macro_time_candidates() -> list[str]:
    """MACRO_TIME 우선, 이후 MACRO_TIME_SLOTS에서 더 늦은 시간 (폴백 off면 MACRO_TIME만)."""
    preferred = normalize_hhmm(MACRO_TIME)
    if not MACRO_TIME_FALLBACK_ENABLED:
        return [preferred]
    slots = [normalize_hhmm(s) for s in MACRO_TIME_SLOTS]
    if not slots:
        return [preferred]
    if preferred in slots:
        return slots[slots.index(preferred):]
    later = [s for s in slots if hhmm_to_minutes(s) > hhmm_to_minutes(preferred)]
    return [preferred, *later]

# 속도 (응답 오면 바로 다음 단계 — sleep 없음, 폴링만)
MACRO_STEP_DELAY = 0
MACRO_WAIT_TIMEOUT = 0.1
MACRO_POLL_INTERVAL = 0.02
MACRO_TIME_CLICK_TIMEOUT = 0.3  # 시간 슬롯 클릭 시도 (마감 시 다음 슬롯으로 빠르게)
MACRO_TIME_LIST_WAIT_TIMEOUT = 15  # 날짜 클릭 후 시간 목록 AJAX 응답 대기(초)
MACRO_TIME_GROUP_RETRY_MAX = 10  # (설정시간→이후시간 전체 스캔) 재시도 횟수
MACRO_TIME_GROUP_RETRY_DELAY = 0.05  # 그룹 재시도 간격(초)
MACRO_ALERT_RETRY_DELAY = 0.05  # 재시도 전 대기(초)
MACRO_ALERT_RETRY_MAX = 100       # 날짜/시간 목록 재시도 최대 횟수
MACRO_MASK_TIMEOUT = 2
MACRO_SUBMIT_TIMEOUT = 10

# ── 서버 시각 자동 실행 ─────────────────────────────────────────
AUTO_RUN_ENABLED = True
AUTO_RUN_AT = "11:00"           # 서버 KST (HH:MM) — 이 시각 이후 실행
AUTO_RUN_MIN_DELAY_MS = 0      # 11:00:00.000+N ms 이후 실행 (0~50, 이전 실행 방지)
SERVER_TIME_SYNC_INTERVAL = 15  # 서버 시각 재동기화 주기(초)
SERVER_TIME_PRE_SYNC_SEC = 30   # 실행 N초 전부터 재동기화 구간
SERVER_TIME_FINAL_SPIN_SEC = 3  # 마지막 N초: HTTP sync 끄고 ms 단위 대기
SERVER_TIME_STALE_MAX_SEC = 2.0 # HTTP Date가 추정보다 느리면 → 시계 뒤로만 보정
SERVER_TIME_MAX_FORWARD_SEC = 0  # sync 1회당 시계 앞당김 상한(초)
SERVER_TIME_TIMEOUT = 5         # HTTP Date 조회 타임아웃(초)

# ── 출력 경로 ───────────────────────────────────────────────────
OUTPUT_DIR = BASE_DIR / "output"
SCREENSHOT_DIR = BASE_DIR / "screenshots"

# ── 사용자 설정 (ui/settings.json) ──────────────────────────────
def _load_user_settings() -> None:
    try:
        from ui.storage import apply_saved_settings

        apply_saved_settings()
    except ImportError:
        pass


_load_user_settings()
