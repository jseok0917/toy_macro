"""
키이스케이프(keyescape.com) 개발자도구 탐지 우회.

사이트가 사용하는 devtools-detector v2.0.22 + inline blockDevTools() 를 무력화합니다.
Selenium/ChromeDriver의 CDP 연결도 'devtools open' 으로 오탐지합니다.
"""

from selenium import webdriver

DEVTOOLS_DETECTOR_URLS = [
    "*devtools-detector*",
    "*cdnjs.cloudflare.com/ajax/libs/devtools-detector/*",
]

# 페이지 JS 실행 전 주입 — CDN 로드 전에 stub 설치
DEVTOOLS_STUB_SCRIPT = """
(() => {
  const noop = () => {};
  const stub = {
    addListener: noop,
    launch: noop,
    stop: noop,
    removeListener: noop,
    isLaunch: () => false,
    setDetectDelay: noop,
  };

  Object.defineProperty(window, "devtoolsDetector", {
    configurable: true,
    enumerable: true,
    get: () => stub,
    set: () => {},
  });

  // inline blockDevTools() 가 body 를 덮어쓰지 못하게 방어
  const blockMsg = "개발자 도구 사용이 금지";
  const origDescriptor = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
  if (origDescriptor && origDescriptor.set) {
    const origSet = origDescriptor.set;
    Object.defineProperty(Element.prototype, "innerHTML", {
      configurable: true,
      enumerable: origDescriptor.enumerable,
      get: origDescriptor.get,
      set: function(value) {
        if (typeof value === "string" && value.includes(blockMsg)) {
          return;
        }
        return origSet.call(this, value);
      },
    });
  }
})();
"""


def apply_keyescape_bypass(driver: webdriver.Chrome) -> None:
    """driver.get() 호출 전에 한 번 실행."""
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": DEVTOOLS_DETECTOR_URLS})
    except Exception as exc:
        print(f"[WARN] Network block 설정 실패: {exc}", flush=True)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": DEVTOOLS_STUB_SCRIPT},
    )
    print("[Bypass] keyescape devtools-detector 우회 적용", flush=True)


def is_keyescape_url(url: str) -> bool:
    return "keyescape.com" in (url or "")
