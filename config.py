import os
import re
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

# Chrome 148 등 — 자동 감지 실패 시 수동 지정
CHROME_VERSION_MAIN = 148

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

# ── 자동등록 방지 (Enter 키) ────────────────────────────────────
CAPTCHA_TIMEOUT = 15
CAPTCHA_WAIT_BEFORE_ENTER = 0
CAPTCHA_SETTLE_WAIT = 0
CAPTCHA_ENTER_RETRY = 1

# CAPTCHA_FOCUS_SELECTOR = "button"
# CAPTCHA_SELECTOR = "#captcha-box"
# SUCCESS_SELECTOR = "#main-content"

# ── 예약자 정보 ─────────────────────────────────────────────────
RESERVATION_NAME = "일이삼"
RESERVATION_PHONE = "1234-0000"   # 010은 페이지 고정, mobile2-mobile3


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
ZIZUM_NUM = 23              # 지점 번호
THEME_NUM = 69              # 테마 번호
THEME_INFO_NUM = 60         # 테마 상세 번호 (theme_info_num)

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
MACRO_DAY_OFFSET = 4          # 서버 SYSDATE + N 일
MACRO_TIME = "09:20"          # 예약 시간 슬롯 (HH:MM)

# 속도 (응답 오면 바로 다음 단계 — sleep 없음, 폴링만)
MACRO_STEP_DELAY = 0
MACRO_WAIT_TIMEOUT = 6
MACRO_POLL_INTERVAL = 0.02
MACRO_MASK_TIMEOUT = 2
MACRO_SUBMIT_TIMEOUT = 10

# ── 서버 시각 자동 실행 ─────────────────────────────────────────
AUTO_RUN_ENABLED = True
AUTO_RUN_AT = "04:06"           # 서버 KST (HH:MM)
SERVER_TIME_SYNC_INTERVAL = 15  # 서버 시각 재동기화 주기(초)
SERVER_TIME_PRE_SYNC_SEC = 30   # 실행 N초 전부터 매 루프 재동기화
SERVER_TIME_TIMEOUT = 5         # HTTP Date 조회 타임아웃(초)

# ── 출력 경로 ───────────────────────────────────────────────────
OUTPUT_DIR = BASE_DIR / "output"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
