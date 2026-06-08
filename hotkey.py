"""F9/Enter 수동 실행 + 서버 시각 자동 실행."""

import ctypes
import queue
import sys
import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Literal

from server_time import ServerClock, format_kst, next_run_at, parse_hhmm, seconds_until

Event = Literal["macro", "exit"]

VK_F9 = 0x78
VK_ESCAPE = 0x1B


def _is_key_down(vk_code: int) -> bool:
    if sys.platform != "win32":
        return False
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


class HotkeyListener:
    def __init__(self, poll_interval: float = 0.05) -> None:
        self._queue: queue.Queue[Event] = queue.Queue()
        self._poll_interval = poll_interval
        self._running = False
        self._f9_was_down = False
        self._esc_was_down = False

    def start(self, *, auto_at: str | None = None) -> None:
        self._running = True
        msg = "[Hotkey] F9=매크로  ESC=종료  Enter=매크로(터미널)"
        if auto_at:
            msg += f"  |  서버시각 {auto_at} 자동실행"
        print(msg, flush=True)

    def stop(self) -> None:
        self._running = False

    def _poll_keys(self) -> None:
        f9_down = _is_key_down(VK_F9)
        if f9_down and not self._f9_was_down:
            print("[Hotkey] F9 감지", flush=True)
            self._queue.put("macro")
        self._f9_was_down = f9_down

        esc_down = _is_key_down(VK_ESCAPE)
        if esc_down and not self._esc_was_down:
            print("[Hotkey] ESC 감지", flush=True)
            self._queue.put("exit")
        self._esc_was_down = esc_down

    def wait_event(self, timeout: float | None = None) -> Event | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _sleep_interval(self, clock: ServerClock, target: datetime | None) -> float:
        if target is None:
            return self._poll_interval
        remaining = seconds_until(target, clock)
        if remaining <= 0:
            return self._poll_interval
        if remaining <= 1.0:
            return 0.005
        if remaining <= 10:
            return 0.01
        if remaining <= 60:
            return 0.05
        if remaining <= 300:
            return 0.25
        return min(10.0, max(1.0, remaining - 30))

    def _check_auto_run(
        self,
        clock: ServerClock,
        hour: int,
        minute: int,
        *,
        next_target: datetime,
        fired_date: date | None,
    ) -> tuple[datetime, date | None, bool]:
        now = clock.now()
        clock.maybe_resync_near(next_target)

        if now >= next_target and fired_date != next_target.date():
            print(f"[Schedule] 서버시각 자동 실행: {format_kst(now)}", flush=True)
            new_target = next_run_at(clock, hour, minute)
            return new_target, next_target.date(), True

        return next_target, fired_date, False

    def run_forever(
        self,
        on_macro: Callable[[], None],
        *,
        server_clock: ServerClock | None = None,
        auto_at: str | None = None,
    ) -> None:
        self.start(auto_at=auto_at)

        hour = minute = 0
        next_target: datetime | None = None
        fired_date: date | None = None
        last_status = 0.0

        if auto_at and server_clock:
            hour, minute = parse_hhmm(auto_at)
            next_target = next_run_at(server_clock, hour, minute)
            print(
                f"[Schedule] 다음 자동 실행: {format_kst(next_target)} "
                f"(현재 서버 {format_kst(server_clock.now())})",
                flush=True,
            )

        stop_input = threading.Event()

        def _terminal_enter_listener() -> None:
            while not stop_input.is_set():
                try:
                    input()
                    if not stop_input.is_set():
                        print("[Hotkey] Enter(터미널) 감지", flush=True)
                        self._queue.put("macro")
                except EOFError:
                    break

        threading.Thread(target=_terminal_enter_listener, daemon=True).start()

        try:
            while self._running:
                if sys.platform == "win32":
                    self._poll_keys()

                interval = self._sleep_interval(server_clock, next_target) if server_clock else self._poll_interval
                event = self.wait_event(timeout=interval)

                if event == "exit":
                    print("[Hotkey] 종료", flush=True)
                    break
                if event == "macro":
                    if server_clock:
                        print(f"[Server] {format_kst(server_clock.now())}", flush=True)
                    on_macro()
                    continue

                if server_clock and next_target and auto_at:
                    next_target, fired_date, triggered = self._check_auto_run(
                        server_clock, hour, minute,
                        next_target=next_target,
                        fired_date=fired_date,
                    )
                    if triggered:
                        on_macro()
                        print(
                            f"[Schedule] 다음 자동 실행: {format_kst(next_target)}",
                            flush=True,
                        )
                        continue

                    now_mono = time.monotonic()
                    if now_mono - last_status >= 60:
                        last_status = now_mono
                        rem = seconds_until(next_target, server_clock)
                        if rem > 0:
                            print(
                                f"[Schedule] 대기 {int(rem // 3600)}h {int((rem % 3600) // 60)}m "
                                f"| 서버 {format_kst(server_clock.now())}",
                                flush=True,
                            )
        finally:
            stop_input.set()
            self.stop()
