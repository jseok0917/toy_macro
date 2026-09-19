"""settings.json ↔ config.py 필드 정의."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldKind = Literal[
    "int",
    "float",
    "bool",
    "str",
    "path",
    "hhmm",
    "choice",
    "time_list",
]
WidgetKind = Literal["default", "macro_time", "multiline"]


@dataclass(frozen=True)
class SettingField:
    key: str
    attr: str | None
    kind: FieldKind
    label: str
    tab: str
    choices: tuple[str, ...] = ()
    widget: WidgetKind = "default"
    min_value: float | None = None
    max_value: float | None = None


SETTING_FIELDS: tuple[SettingField, ...] = (
    # ── 예약 ──
    SettingField("zizum_num", "ZIZUM_NUM", "int", "지점 번호 (zizum_num)", "예약", min_value=1),
    SettingField("theme_num", "THEME_NUM", "int", "테마 번호 (theme_num)", "예약", min_value=1),
    SettingField(
        "theme_info_num", "THEME_INFO_NUM", "int", "테마 상세 (theme_info_num)", "예약", min_value=1
    ),
    SettingField("reservation_name", "RESERVATION_NAME", "str", "예약자 이름", "예약"),
    SettingField(
        "reservation_phone", "RESERVATION_PHONE", "str", "연락처 (010-XXXX-XXXX)", "예약"
    ),
    SettingField(
        "reservation_base_url", "RESERVATION_BASE_URL", "str", "예약 페이지 URL", "예약"
    ),
    SettingField(
        "macro_day_offset",
        "MACRO_DAY_OFFSET",
        "int",
        "예약 날짜 (서버 SYSDATE + N일)",
        "예약",
        min_value=0,
    ),
    SettingField("macro_time", "MACRO_TIME", "hhmm", "예약 시간 (HH:MM)", "예약", widget="macro_time"),
    SettingField(
        "macro_time_fallback_enabled",
        "MACRO_TIME_FALLBACK_ENABLED",
        "bool",
        "마감 시 이후 시간대 중 자동예약",
        "예약",
    ),
    SettingField(
        "macro_time_slots",
        "MACRO_TIME_SLOTS",
        "time_list",
        "시간 슬롯 목록 (비우면 실행 시 API 조회)",
        "예약",
        widget="multiline",
    ),
    SettingField("macro_hotkey", "MACRO_HOTKEY", "str", "매크로 핫키", "예약"),
    # ── 매크로 튜닝 ──
    SettingField(
        "macro_step_delay", "MACRO_STEP_DELAY", "float", "단계 간 지연(초)", "매크로", min_value=0
    ),
    SettingField(
        "macro_wait_timeout", "MACRO_WAIT_TIMEOUT", "float", "대기 타임아웃(초)", "매크로", min_value=0
    ),
    SettingField(
        "macro_poll_interval",
        "MACRO_POLL_INTERVAL",
        "float",
        "폴링 간격(초)",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_time_click_timeout",
        "MACRO_TIME_CLICK_TIMEOUT",
        "float",
        "시간 슬롯 클릭 타임아웃(초)",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_time_list_wait_timeout",
        "MACRO_TIME_LIST_WAIT_TIMEOUT",
        "float",
        "시간 목록 AJAX 대기(초)",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_time_group_retry_max",
        "MACRO_TIME_GROUP_RETRY_MAX",
        "int",
        "시간 그룹 재시도 횟수",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_time_group_retry_delay",
        "MACRO_TIME_GROUP_RETRY_DELAY",
        "float",
        "시간 그룹 재시도 간격(초)",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_alert_retry_delay",
        "MACRO_ALERT_RETRY_DELAY",
        "float",
        "알림 재시도 전 대기(초)",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_alert_retry_max",
        "MACRO_ALERT_RETRY_MAX",
        "int",
        "날짜/시간 목록 재시도 최대",
        "매크로",
        min_value=0,
    ),
    SettingField(
        "macro_mask_timeout", "MACRO_MASK_TIMEOUT", "float", "마스크 타임아웃(초)", "매크로", min_value=0
    ),
    SettingField(
        "macro_submit_timeout",
        "MACRO_SUBMIT_TIMEOUT",
        "float",
        "제출 타임아웃(초)",
        "매크로",
        min_value=0,
    ),
    # ── 서버 시각 / 자동 실행 ──
    SettingField(
        "auto_run_enabled", "AUTO_RUN_ENABLED", "bool", "서버 시각 자동 실행", "서버 시각"
    ),
    SettingField(
        "auto_run_at", "AUTO_RUN_AT", "hhmm", "자동 실행 시각 (서버 KST, HH:MM)", "서버 시각"
    ),
    SettingField(
        "auto_run_min_delay_ms",
        "AUTO_RUN_MIN_DELAY_MS",
        "int",
        "자동 실행 최소 지연(ms, 0~50)",
        "서버 시각",
        min_value=0,
        max_value=50,
    ),
    SettingField(
        "server_time_sync_interval",
        "SERVER_TIME_SYNC_INTERVAL",
        "int",
        "서버 시각 재동기화 주기(초)",
        "서버 시각",
        min_value=1,
    ),
    SettingField(
        "server_time_pre_sync_sec",
        "SERVER_TIME_PRE_SYNC_SEC",
        "int",
        "실행 전 재동기화 시작(초 전)",
        "서버 시각",
        min_value=0,
    ),
    SettingField(
        "server_time_final_spin_sec",
        "SERVER_TIME_FINAL_SPIN_SEC",
        "int",
        "마지막 고정밀 대기 구간(초)",
        "서버 시각",
        min_value=0,
    ),
    SettingField(
        "server_time_stale_max_sec",
        "SERVER_TIME_STALE_MAX_SEC",
        "float",
        "HTTP Date stale 상한(초)",
        "서버 시각",
        min_value=0,
    ),
    SettingField(
        "server_time_max_forward_sec",
        "SERVER_TIME_MAX_FORWARD_SEC",
        "float",
        "sync 1회 앞당김 상한(초)",
        "서버 시각",
        min_value=0,
    ),
    SettingField(
        "server_time_timeout",
        "SERVER_TIME_TIMEOUT",
        "float",
        "HTTP Date 조회 타임아웃(초)",
        "서버 시각",
        min_value=1,
    ),
    # ── CAPTCHA ──
    SettingField(
        "captcha_timeout", "CAPTCHA_TIMEOUT", "int", "CAPTCHA 타임아웃(초)", "CAPTCHA", min_value=0
    ),
    SettingField(
        "recaptcha_wait_timeout",
        "RECAPTCHA_WAIT_TIMEOUT",
        "int",
        "reCAPTCHA 자동 통과 최대 대기(초)",
        "CAPTCHA",
        min_value=0,
    ),
    SettingField(
        "captcha_wait_before_enter",
        "CAPTCHA_WAIT_BEFORE_ENTER",
        "float",
        "Enter 전 대기(초)",
        "CAPTCHA",
        min_value=0,
    ),
    SettingField(
        "captcha_settle_wait",
        "CAPTCHA_SETTLE_WAIT",
        "float",
        "CAPTCHA 안정화 대기(초)",
        "CAPTCHA",
        min_value=0,
    ),
    SettingField(
        "captcha_enter_retry",
        "CAPTCHA_ENTER_RETRY",
        "int",
        "Enter 재시도 횟수",
        "CAPTCHA",
        min_value=0,
    ),
)

SETTING_KEYS = frozenset(f.key for f in SETTING_FIELDS)

TAB_ORDER = ("예약", "매크로", "서버 시각", "CAPTCHA")

FIELDS_BY_TAB: dict[str, list[SettingField]] = {}
for _field in SETTING_FIELDS:
    FIELDS_BY_TAB.setdefault(_field.tab, []).append(_field)

FIELD_BY_KEY = {f.key: f for f in SETTING_FIELDS}
