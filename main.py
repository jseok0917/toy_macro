"""
Chrome + Selenium + F9 매크로

사용법:
    run.bat                  # 키이스케이프 접속 → F9 대기
    run.bat --once           # 접속만 하고 종료
    run.bat --current        # 열린 Chrome 탭 (키이스케이프 attach 비권장)
"""

import argparse
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import config
from browser import create_driver, create_wait
from hotkey import HotkeyListener
from keyescape_bypass import apply_keyescape_bypass, is_keyescape_url
from keyescape_api import format_slots_display
from macro import run_macro
from server_time import ServerClock, format_kst
from tab_utils import attach_current_tab, print_debug_tabs


def resolve_reservation_url(args: argparse.Namespace) -> str:
    """CLI 옵션이 있으면 우선, 없으면 config 변수 사용."""
    if args.url:
        return args.url
    return config.build_reservation_url(
        zizum_num=args.zizum_num,
        theme_num=args.theme_num,
        theme_info_num=args.theme_info_num,
    )


def print_reservation_config(url: str, *, auto_at: str | None, auto_enabled: bool) -> None:
    schedule = auto_at if auto_enabled and auto_at else "비활성"
    print("[Config] 예약 설정", flush=True)
    print(f"  지점 zizum_num      = {config.ZIZUM_NUM}", flush=True)
    print(f"  테마 theme_num      = {config.THEME_NUM}", flush=True)
    print(f"  상세 theme_info_num = {config.THEME_INFO_NUM}", flush=True)
    print(f"  예약 날짜           = 서버 SYSDATE+{config.MACRO_DAY_OFFSET}", flush=True)
    print(f"  예약 시간           = {config.MACRO_TIME}", flush=True)
    fallback = "켜짐" if config.MACRO_TIME_FALLBACK_ENABLED else "꺼짐"
    print(f"  이후 슬롯 자동      = {fallback}", flush=True)
    print(f"  예약자              = {config.RESERVATION_NAME}", flush=True)
    print(f"  연락처              = 010-{config.RESERVATION_PHONE}", flush=True)
    print(f"  자동 실행           = {schedule} (서버 KST)", flush=True)
    print(f"  URL                 = {url}", flush=True)
    try:
        from server_time import fetch_server_now

        server_now = fetch_server_now()
        slots = config.refresh_macro_time_slots(
            date=server_now.strftime("%Y-%m-%d"),
        )
        print(f"  서버 SYSDATE        = {server_now.strftime('%Y-%m-%d')}", flush=True)
        print(f"  시간 슬롯 ({len(slots)}개)  = {format_slots_display(slots)}", flush=True)
    except Exception as exc:
        print(f"  [WARN] 시간 슬롯 API 조회 실패: {exc}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="키이스케이프 Selenium 매크로")
    parser.add_argument(
        "--url",
        default=None,
        help="접속 URL (미지정 시 config ZIZUM/THEME/THEME_INFO 사용)",
    )
    parser.add_argument(
        "--zizum-num",
        type=int,
        default=None,
        help=f"지점 번호 (기본: config.ZIZUM_NUM={config.ZIZUM_NUM})",
    )
    parser.add_argument(
        "--theme-num",
        type=int,
        default=None,
        help=f"테마 번호 (기본: config.THEME_NUM={config.THEME_NUM})",
    )
    parser.add_argument(
        "--theme-info-num",
        type=int,
        default=None,
        help=f"테마 상세 번호 (기본: config.THEME_INFO_NUM={config.THEME_INFO_NUM})",
    )
    parser.add_argument("--current", action="store_true", help="열린 Chrome 탭 사용")
    parser.add_argument("--attach", action="store_true", help="(--current 호환)")
    parser.add_argument("--tab-url", default=None)
    parser.add_argument("--tab-title", default=None)
    parser.add_argument("--tab-index", type=int, default=None)
    parser.add_argument("--list-tabs", action="store_true")
    parser.add_argument("--new-window", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--close", action="store_true", help="종료 시 Chrome 닫기")
    parser.add_argument(
        "--once",
        action="store_true",
        help="F9 대기 없이 접속 후 바로 종료",
    )
    parser.add_argument(
        "--auto-at",
        default=None,
        metavar="HH:MM",
        help=f"서버 KST 자동 실행 시각 (기본: config.AUTO_RUN_AT={config.AUTO_RUN_AT})",
    )
    parser.add_argument(
        "--no-auto",
        action="store_true",
        help="자동 실행 비활성화 (F9/Enter 만)",
    )
    parser.add_argument(
        "--show-server-time",
        action="store_true",
        help="서버 시각 출력 후 종료",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="설정 UI 건너뛰기 (run.bat에서 사용)",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="설정 UI 강제 표시 (run.bat에서 사용)",
    )
    return parser.parse_args()


def open_keyescape(
    driver: webdriver.Chrome,
    *,
    url: str,
    use_current_tab: bool = False,
    tab_url: str | None = None,
    tab_title: str | None = None,
    tab_index: int | None = None,
) -> dict:
    wait = create_wait(driver)
    target_url = url

    if is_keyescape_url(target_url) and not use_current_tab:
        apply_keyescape_bypass(driver)

    if use_current_tab:
        attach_current_tab(
            driver,
            url_contains=tab_url,
            title_contains=tab_title,
            tab_index=tab_index,
        )
    else:
        driver.get(target_url)

    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    if is_keyescape_url(driver.current_url):
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "개발자 도구 사용이 금지" in body_text:
            print("[WARN] devtools 차단 — chrome_profile 삭제 후 재실행", flush=True)

    result = {"url": driver.current_url, "title": driver.title}
    print(f"[OK] 접속: {result['url']}")
    print(f"[OK] 제목: {result['title']}")
    return result


def run_session(
    *,
    url: str,
    use_current_tab: bool = False,
    tab_url: str | None = None,
    tab_title: str | None = None,
    tab_index: int | None = None,
    headless: bool = False,
    new_window: bool = False,
    keep_open: bool = True,
    wait_hotkey: bool = True,
    auto_at: str | None = None,
    auto_enabled: bool = True,
) -> None:
    mode = "attach" if use_current_tab else "profile"
    driver = create_driver(headless=headless, mode=mode, keep_open=keep_open)

    try:
        open_keyescape(
            driver,
            url=url,
            use_current_tab=use_current_tab,
            tab_url=tab_url,
            tab_title=tab_title,
            tab_index=tab_index,
        )

        if not wait_hotkey:
            return

        clock = ServerClock()
        try:
            server_now = clock.sync(force=True)
            print(f"[Server] 현재 서버 시각: {format_kst(server_now)}", flush=True)
        except RuntimeError as exc:
            print(f"[WARN] {exc} — 로컬 시각으로 자동 실행", flush=True)
            clock = None

        use_auto = auto_enabled and (auto_at or config.AUTO_RUN_ENABLED)
        schedule_at = auto_at or (config.AUTO_RUN_AT if config.AUTO_RUN_ENABLED else None)
        if use_auto and not schedule_at:
            use_auto = False

        print("[Ready] F9 / Enter 수동 실행 가능", flush=True)
        HotkeyListener().run_forever(
            on_macro=lambda: run_macro(driver, server_clock=clock),
            server_clock=clock,
            auto_at=schedule_at if use_auto else None,
        )
    finally:
        if keep_open:
            try:
                driver.service.stop()
            except Exception:
                pass
        else:
            driver.quit()


def main() -> int:
    args = parse_args()
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.SCREENSHOT_DIR.mkdir(exist_ok=True)

    if args.list_tabs:
        try:
            print_debug_tabs()
            return 0
        except Exception as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

    if args.show_server_time:
        try:
            clock = ServerClock()
            print(format_kst(clock.sync(force=True)))
            return 0
        except RuntimeError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

    use_current = args.current or args.attach
    auto_at = args.auto_at
    auto_enabled = not args.no_auto
    url = resolve_reservation_url(args)
    schedule_at = auto_at or (config.AUTO_RUN_AT if config.AUTO_RUN_ENABLED else None)
    if not auto_enabled:
        schedule_at = None

    print_reservation_config(url, auto_at=schedule_at, auto_enabled=auto_enabled)

    try:
        run_session(
            url=url,
            use_current_tab=use_current and not args.new_window,
            tab_url=args.tab_url,
            tab_title=args.tab_title,
            tab_index=args.tab_index,
            headless=args.headless,
            new_window=args.new_window,
            keep_open=not args.close,
            wait_hotkey=not args.once,
            auto_at=auto_at or (config.AUTO_RUN_AT if auto_enabled else None),
            auto_enabled=auto_enabled,
        )
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
