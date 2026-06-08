"""키이스케이프 서버 시간 (HTTP Date → KST)."""

from __future__ import annotations

import email.utils
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import config

KST = timezone(timedelta(hours=9))
TIME_URL = "https://www.keyescape.com/"


def fetch_server_now() -> datetime:
    """HTTP Date 헤더 기준 서버 시각 (KST)."""
    req = urllib.request.Request(
        TIME_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=config.SERVER_TIME_TIMEOUT) as resp:
        raw = resp.headers.get("Date")
        if not raw:
            raise RuntimeError("Date 헤더 없음")
        return email.utils.parsedate_to_datetime(raw).astimezone(KST)


class ServerClock:
    """로컬 시계 + 서버 offset 으로 KST 추정 (네트워크 호출 최소화)."""

    def __init__(self) -> None:
        self._offset_sec: float = 0.0
        self._last_sync: float = 0.0

    def sync(self, force: bool = False) -> datetime:
        interval = config.SERVER_TIME_SYNC_INTERVAL
        if not force and time.monotonic() - self._last_sync < interval:
            return self.now()

        local_mid = time.time()
        try:
            server = fetch_server_now()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"서버 시간 조회 실패: {exc}") from exc

        self._offset_sec = server.timestamp() - local_mid
        self._last_sync = time.monotonic()
        return server

    def now(self) -> datetime:
        return datetime.fromtimestamp(
            time.time() + self._offset_sec,
            tz=KST,
        )

    def maybe_resync_near(self, target: datetime) -> None:
        """자동 실행 직전 정밀 동기화."""
        remaining = (target - self.now()).total_seconds()
        if remaining <= 0:
            return
        if remaining <= config.SERVER_TIME_PRE_SYNC_SEC:
            self.sync(force=True)
        elif remaining <= config.SERVER_TIME_PRE_SYNC_SEC * 2:
            # 임박 구간: 주기보다 자주 동기화
            if time.monotonic() - self._last_sync >= min(5, config.SERVER_TIME_SYNC_INTERVAL):
                self.sync(force=True)


def parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"시간 형식 오류 (HH:MM): {value}")
    return int(parts[0]), int(parts[1])


def next_run_at(clock: ServerClock, hour: int, minute: int) -> datetime:
    """다음 실행 시각 (오늘 해당 시각이 지났으면 내일)."""
    now = clock.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def format_kst(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S KST")


def seconds_until(target: datetime, clock: ServerClock) -> float:
    return (target - clock.now()).total_seconds()
