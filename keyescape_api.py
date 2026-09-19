"""keyescape.com run_proc.php API (브라우저 없이 조회)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

API_URL = "https://www.keyescape.com/controller/run_proc.php"
API_TIMEOUT = 15


@dataclass(frozen=True)
class ThemeTimeSlot:
    time: str  # HH:MM
    available: bool
    num: int


def post_run_proc(params: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        return json.loads(resp.read())


def fetch_theme_time_slots(
    date: str,
    *,
    zizum_num: int | str,
    theme_num: int | str,
    end_day: int | str = 0,
) -> list[ThemeTimeSlot]:
    """지정 날짜의 테마 시간 슬롯 (get_theme_time)."""
    result = post_run_proc(
        {
            "t": "get_theme_time",
            "date": date,
            "zizumNum": str(zizum_num),
            "themeNum": str(theme_num),
            "endDay": str(end_day),
        }
    )
    if not result.get("status"):
        msg = result.get("msg") or "알 수 없는 오류"
        raise RuntimeError(f"get_theme_time 실패: {msg}")

    rows = result.get("data") or []
    slots: list[ThemeTimeSlot] = []
    for row in rows:
        hh = str(row.get("hh", "")).zfill(2)
        mm = str(row.get("mm", "")).zfill(2)
        slots.append(
            ThemeTimeSlot(
                time=f"{int(hh):02d}:{int(mm):02d}",
                available=str(row.get("enable", "")).upper() == "Y",
                num=int(row["num"]),
            )
        )
    return slots


def format_slots_display(slots: list[ThemeTimeSlot]) -> str:
    times = [s.time for s in slots]
    return ", ".join(times) if times else "(없음)"
