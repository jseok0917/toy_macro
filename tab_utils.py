"""실행 중인 Chrome 탭 조회·전환."""

import json
import urllib.error
import urllib.request

from selenium import webdriver

import config


def is_debug_chrome_running(address: str | None = None) -> bool:
    addr = address or config.DEBUGGER_ADDRESS
    try:
        with urllib.request.urlopen(f"http://{addr}/json/version", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def list_debug_tabs(address: str | None = None) -> list[dict]:
    addr = address or config.DEBUGGER_ADDRESS
    with urllib.request.urlopen(f"http://{addr}/json/list", timeout=5) as resp:
        tabs = json.loads(resp.read())
    return [t for t in tabs if t.get("type") == "page"]


def print_debug_tabs(address: str | None = None) -> None:
    tabs = list_debug_tabs(address)
    if not tabs:
        print("[INFO] 열린 탭 없음", flush=True)
        return

    print(f"[INFO] Chrome 탭 {len(tabs)}개:", flush=True)
    for i, tab in enumerate(tabs):
        title = tab.get("title") or "(제목 없음)"
        url = tab.get("url") or ""
        print(f"  [{i}] {title}", flush=True)
        print(f"       {url}", flush=True)


def switch_to_tab(
    driver: webdriver.Chrome,
    *,
    url_contains: str | None = None,
    title_contains: str | None = None,
    tab_index: int | None = None,
) -> str:
    """열린 탭 중 하나로 전환합니다."""
    handles = driver.window_handles
    if not handles:
        raise RuntimeError("연결된 Chrome 탭이 없습니다.")

    if tab_index is not None:
        if tab_index < 0 or tab_index >= len(handles):
            raise IndexError(f"탭 인덱스 {tab_index}는 0~{len(handles) - 1} 범위여야 합니다.")
        driver.switch_to.window(handles[tab_index])
        return handles[tab_index]

    if url_contains or title_contains:
        for handle in handles:
            driver.switch_to.window(handle)
            if url_contains and url_contains in driver.current_url:
                return handle
            if title_contains and title_contains in driver.title:
                return handle
        hint = url_contains or title_contains
        raise RuntimeError(f"'{hint}'(와)과 일치하는 탭을 찾지 못했습니다. --list-tabs 로 확인하세요.")

    # 조건 없으면 마지막 탭(보통 가장 최근에 연 탭)
    driver.switch_to.window(handles[-1])
    return handles[-1]


def attach_current_tab(
    driver: webdriver.Chrome,
    *,
    url_contains: str | None = None,
    title_contains: str | None = None,
    tab_index: int | None = None,
) -> dict:
    """새 창 없이, 이미 열려 있는 탭을 그대로 사용합니다."""
    handle = switch_to_tab(
        driver,
        url_contains=url_contains,
        title_contains=title_contains,
        tab_index=tab_index,
    )

    info = {
        "handle": handle,
        "url": driver.current_url,
        "title": driver.title,
    }
    print(f"[OK] 현재 탭: {info['title']}", flush=True)
    print(f"     {info['url']}", flush=True)
    return info
