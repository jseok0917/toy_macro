---
name: keyescape-devtools-bypass
description: Bypasses keyescape.com devtools-detector blocking for Selenium automation. Use when seeing "개발자 도구 사용이 금지", devtools-detector, black screen, or Selenium blocked on keyescape.
---

# Keyescape Devtools Bypass

## Symptom

Black full-page overlay: "개발자 도구 사용이 금지되어 있습니다."

## Cause

- Page loads `devtools-detector` v2.0.22 from cdnjs
- Detects CDP/debugger/console timing — triggers even with F12 closed when using ChromeDriver

## Fix (already in project)

Call **before** `driver.get()`:

```python
from keyescape_bypass import apply_keyescape_bypass, is_keyescape_url

if is_keyescape_url(url):
    apply_keyescape_bypass(driver)
driver.get(url)
```

Implementation in `keyescape_bypass.py`:

1. `Network.setBlockedURLs` — block `*devtools-detector*`
2. `Page.addScriptToEvaluateOnNewDocument` — stub `window.devtoolsDetector`
3. Patch `innerHTML` setter to ignore block message

## If still blocked

1. Delete `chrome_profile/` and rerun `.\run.bat`
2. Confirm `config.USE_UNDETECTED = True`
3. Do **not** use `--current` / `start_chrome.bat` (debug port triggers detection)

## Verify

```python
body = driver.find_element(By.TAG_NAME, "body").text
assert "개발자 도구 사용이 금지" not in body
assert driver.find_elements(By.ID, "resrvPage") or driver.find_elements(By.CSS_SELECTOR, ".selDate")
```

## Extending bypass

- If site updates detector version, update `DEVTOOLS_DETECTOR_URLS` patterns
- Do not remove bypass for keyescape URLs in `open_keyescape()`
