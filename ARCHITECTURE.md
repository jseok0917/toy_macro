# Keyscape 예약 매크로 — 아키텍처 & 기술 문서

> [keyescape.com](https://www.keyescape.com) 방탈출 예약을 자동화하는 Selenium 매크로 프로젝트  
> Python + undetected-chromedriver + CDP 우회 + 서버 시각 스케줄링

---

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [모듈 구성](#3-모듈-구성)
4. [실행 흐름](#4-실행-흐름)
5. [예약 매크로 상세](#5-예약-매크로-상세)
6. [서버 시각 자동 실행](#6-서버-시각-자동-실행)
7. [개발자도구 탐지 우회 (핵심)](#7-개발자도구-탐지-우회-핵심)
8. [기술 스택 & 설계 원칙](#8-기술-스택--설계-원칙)
9. [설정 가이드 (settings.json + UI)](#9-설정-가이드-settingsjson--ui)
10. [실행 방법](#10-실행-방법)
11. [트러블슈팅](#11-트러블슈팅)

---

## 1. 한 줄 요약

```
run.bat → [설정 UI] → settings.json 저장 → Chrome(uc) 실행 → devtools 우회 주입
       → 예약 페이지 접속 → F9 / 서버시각 AUTO_RUN_AT / Enter
       → macro.py가 1~3단계 예약 자동 수행
```

키이스케이프는 **Selenium(ChromeDriver) 사용 자체를 개발자도구로 간주**해 페이지를 차단한다.  
그래서 **3겹 방어**를 쓴다:

| 계층 | 역할 |
|------|------|
| `undetected-chromedriver` | ChromeDriver/Selenium 흔적 최소화 |
| `keyescape_bypass.py` | 사이트 devtools-detector 무력화 |
| `profile` 모드 | 디버그 포트(9222) attach 금지 |

---

## 2. 전체 아키텍처

### 2.1 시스템 구성도

```mermaid
flowchart TB
    subgraph User["사용자"]
        BAT[run.bat]
        SET[settings.bat]
        F9[F9 키]
        ENT[터미널 Enter]
    end

    subgraph Settings["설정 (별도 프로세스)"]
        UI[ui/app_tk.py]
        JSON[settings.json]
    end

    subgraph Python["Python 프로세스 (main.py)"]
        CFG[config.py]
        MAIN[main.py]
        HK[hotkey.py]
        CLK[server_time.py]
        MAC[macro.py]
        BYP[keyescape_bypass.py]
        BR[browser.py]
        MW[manual_wait.py]
    end

    subgraph Browser["Chrome (undetected-chromedriver)"]
        PROF[chrome_profile/]
        PAGE[keyescape.com]
    end

    subgraph Site["키이스케이프 서버"]
        R1[reservation1.php]
        R2[reservation2.php]
        R3[reservation3.php]
        API[run_proc.php]
    end

    BAT --> UI
    SET --> UI
    UI -->|저장| JSON
    JSON -->|import 시 로드| CFG
    BAT --> MAIN
    MAIN --> BR
    MAIN --> BYP
    MAIN --> HK
    HK --> CLK
    F9 --> HK
    ENT --> HK
    HK -->|on_macro| MAC
    CLK -->|now / sync| HK
    CLK -->|날짜 offset| MAC
    MAC --> PAGE
    BR --> PROF
    BYP -->|CDP 주입| PAGE
    PAGE --> R1 --> R2 --> R3
    R2 -->|AJAX POST| API
```

### 2.2 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│  Presentation   run.bat, settings.bat, CLI 옵션          │
├─────────────────────────────────────────────────────────┤
│  Settings UI    ui/app_tk.py — tkinter 설정 창           │
│                 ui/storage.py — settings.json I/O          │
├─────────────────────────────────────────────────────────┤
│  Orchestration  main.py — 세션 시작, bypass, hotkey 루프 │
├─────────────────────────────────────────────────────────┤
│  Automation     macro.py — 페이지 클릭/입력/제출         │
│  Scheduling     hotkey.py + server_time.py              │
│  API 조회       keyescape_api.py — 시간 슬롯 등         │
├─────────────────────────────────────────────────────────┤
│  Browser        browser.py — uc Chrome 생성              │
│  Bypass         keyescape_bypass.py — CDP 2단계 우회     │
├─────────────────────────────────────────────────────────┤
│  Config         config.py 기본값 + settings.json 덮어쓰기 │
└─────────────────────────────────────────────────────────┘
```

### 2.3 파일 의존 관계

```mermaid
flowchart LR
    runbat[run.bat] --> uitk[ui/app_tk.py]
    uitk --> storage[ui/storage.py]
    storage --> json[(settings.json)]
    json --> config[config.py]
    runbat --> main[main.py]
    main --> config
    main --> browser[browser.py]
    main --> bypass[keyescape_bypass.py]
    main --> hotkey[hotkey.py]
    main --> macro[macro.py]
    main --> api[keyescape_api.py]
    hotkey --> server[server_time.py]
    macro --> config
    macro --> bypass
    macro --> manual[manual_wait.py]
    config --> api
    browser --> config
    bypass --> selenium[(Selenium CDP)]
    browser --> uc[(undetected-chromedriver)]
```

---

## 3. 모듈 구성

| 파일 | 역할 |
|------|------|
| `run.bat` | 설정 UI(선택) → venv Python으로 `main.py` 실행 |
| `settings.bat` | 설정 UI만 실행 (`python -m ui.app_tk --settings`) |
| `main.py` | CLI 파싱, Chrome 세션, bypass 적용, hotkey 루프 |
| `config.py` | 코드 기본값 + 함수; import 시 `settings.json` 반영 |
| `settings.json` | UI로 편집하는 사용자 설정 (gitignore) |
| `ui/app_tk.py` | tkinter 설정 창 (7개 탭, 스크롤 폼) |
| `ui/schema.py` | 설정 필드 스키마 (51개 항목) |
| `ui/storage.py` | `settings.json` 읽기/검증/저장/`config` 반영 |
| `browser.py` | `undetected-chromedriver` / attach / standard Chrome 생성 |
| `keyescape_bypass.py` | devtools-detector CDN 차단 + JS stub + innerHTML 방어 |
| `keyescape_api.py` | `run_proc.php` HTTP 조회 (시간 슬롯 등) |
| `macro.py` | 예약 1→2→3단계 자동화 (F9 트리거) |
| `hotkey.py` | F9/ESC 폴링, 터미널 Enter, 서버 시각 자동 실행 |
| `server_time.py` | HTTP `Date` 헤더 → KST, offset 기반 `now()` |
| `manual_wait.py` | reCAPTCHA Enter 키 전송 유틸 |
| `tab_utils.py` | attach 모드 탭 선택 (키이스케이프 비권장) |
| `start_chrome.bat` | 디버그 Chrome (9222) — **키이스케이프 사용 금지** |

---

## 4. 실행 흐름

### 4.1 앱 시작 ~ 대기

```mermaid
sequenceDiagram
    participant U as 사용자
    participant M as main.py
    participant B as browser.py
    participant Y as keyescape_bypass
    participant H as hotkey.py
    participant S as server_time.py

    U->>M: run.bat
    Note over U,M: (선택) ui/app_tk → settings.json 저장
    M->>B: create_driver(profile + uc)
    B-->>M: Chrome driver
    M->>Y: apply_keyescape_bypass()  ※ get() 전
    M->>M: driver.get(reservation1 URL)
    M->>S: ServerClock.sync()
    S-->>M: 서버 KST 시각
    M->>H: run_forever(on_macro=run_macro)
    loop 대기 루프
        H->>H: F9/ESC 폴링
        H->>H: 서버시각 >= AUTO_RUN_AT ?
    end
```

### 4.2 매크로 트리거

| 트리거 | 동작 |
|--------|------|
| **F9** | Windows `GetAsyncKeyState` 폴링 |
| **터미널 Enter** | 별도 daemon 스레드 `input()` |
| **서버 시각** | `AUTO_RUN_AT` (예: 11:00 KST) 도달 시 자동 |

> Selenium 호출은 **반드시 메인 스레드**에서만 실행 (`hotkey.py` → `on_macro()` 콜백).

### 4.3 예약 페이지 흐름 (사이트)

```mermaid
flowchart LR
    A[reservation1.php] -->|날짜·시간·NEXT| B[reservation2.php]
    B -->|폼+reCAPTCHA+예약하기| C[run_proc.php AJAX]
    C -->|성공| D[reservation3.php]
```

---

## 5. 예약 매크로 상세

`macro.py` → `run_macro()` 가 핵심. 현재 URL에 따라 분기:

```mermaid
flowchart TD
    START[run_macro 시작] --> URL{현재 URL}
    URL -->|reservation1.php| S1[1단계: 날짜·시간·NEXT]
    URL -->|reservation2.php| S2[2단계만]
    S1 --> S2
    S2 --> DONE[완료]

    subgraph Step1["1단계 reservation1"]
        D1[SYSDATE+N 날짜 클릭]
        D2[MACRO_TIME 슬롯 클릭]
        D3[.btn_next_step → reservation2]
        D1 --> D2 --> D3
    end

    subgraph Step2["2단계 reservation2"]
        F1[이름·연락처·동의 JS 일괄 입력]
        F2[reCAPTCHA Enter]
        F3[예약하기 클릭]
        F4[reservation3.php 대기]
        F1 --> F2 --> F3 --> F4
    end
```

### 5.1 1단계 — 날짜·시간 선택

| 단계 | 셀렉터 / 동작 |
|------|----------------|
| 날짜 | `.selDate.available[data-date='YYYY-MM-DD']` |
| AJAX 대기 | `#mask` 해제 + `#datepicker.timepicker .timeList` (JS 폴링) |
| 시간 | `input.selThemeTimeNum` 활성 + `span`이 `MACRO_TIME`으로 시작 |
| NEXT | `.btn_next_step` → URL에 `reservation2.php` |

- **날짜 계산**: `ServerClock.now().date() + MACRO_DAY_OFFSET` (서버 SYSDATE 기준)
- **속도**: 고정 `sleep` 없음, `MACRO_POLL_INTERVAL`(0.02s) 폴링만 사용
- **클릭**: `executeScript click` — scroll + native click보다 빠름

### 5.2 2단계 — 예약자 정보 & 제출

| 항목 | 처리 |
|------|------|
| 예약자 | `#name_input` ← `config.RESERVATION_NAME` |
| 연락처 | `mobile1=010`(고정), `mobile2`/`mobile3` ← `config.RESERVATION_PHONE` |
| 동의 | `agree_1`(개인정보), `agree_2`(결제 주의) — JS로 `checked=true` |
| reCAPTCHA | iframe anchor 클릭 → `body`에 Enter → `grecaptcha.getResponse()` 폴링 |
| 제출 | `button.submit` 클릭 → `reservation3.php` URL 또는 alert 확인 |

폼 입력은 **한 번의 `execute_script`** 로 일괄 처리 (`_fill_form_batch`).

### 5.3 동시 실행 방지

```python
_lock + _running  # F9 연타 / 자동+수동 중복 실행 방지
driver.implicitly_wait(0)  # 매크로 중 10초 블로킹 방지
```

---

## 6. 서버 시각 자동 실행

키이스케이프 예약 오픈 시각은 **서버 KST** 기준이므로 PC 시계만 믿으면 안 된다.

### 6.1 ServerClock 원리

```mermaid
flowchart LR
    A[HTTP GET keyescape.com] --> B[Date 헤더 파싱]
    B --> C[offset = server_ts - local_ts]
    C --> D[now = time.time + offset → KST]
```

```python
# server_time.py 핵심
offset = server.timestamp() - local_mid
now()  = datetime.fromtimestamp(time.time() + offset, tz=KST)
```

- **초기 sync**: 세션 시작 시 1회 HTTP 조회
- **주기 sync**: `SERVER_TIME_SYNC_INTERVAL`(15초)마다
- **임박 sync**: `AUTO_RUN_AT` 30초 전부터 매 루프 강제 재동기화

### 6.2 스케줄 폴링 (hotkey.py)

남은 시간에 따라 루프 간격을 줄인 **적응형 polling**:

| 남은 시간 | 폴링 간격 |
|-----------|-----------|
| 5분 이상 | 최대 10초 |
| 5분 ~ 1분 | 250ms |
| 1분 ~ 10초 | 50ms |
| 10초 ~ 1초 | 10ms |
| 1초 이내 | **5ms** |

조건: `server_clock.now() >= next_target(AUTO_RUN_AT)` → `run_macro()` 실행  
(하루 1회만 발동 — `fired_date`로 중복 방지)

---

## 7. 개발자도구 탐지 우회 (핵심)

이 섹션이 프로젝트의 **가장 어려운 기술적 문제**다.

### 7.1 문제: 왜 Selenium만 켜도 차단되나?

키이스케이프는 페이지 하단에 다음을 로드한다:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/devtools-detector/2.0.22/devtools-detector.min.js"></script>
<script>
  devtoolsDetector.addListener((isOpen) => {
    if (isOpen) blockDevTools();
  });
  devtoolsDetector.launch();
</script>
```

`blockDevTools()`는 **페이지 전체를 검은 화면으로 덮어씀**:

```javascript
document.body.innerHTML = '...개발자 도구 사용이 금지되어 있습니다....';
```

#### devtools-detector가 "열렸다"고 판단하는 경우

| 상황 | 탐지 여부 |
|------|-----------|
| F12로 DevTools 직접 열기 | ✅ 탐지 |
| Chrome `--remote-debugging-port=9222` (attach) | ✅ 탐지 |
| **Selenium ChromeDriver (CDP 연결)** | ✅ **오탐지** — DevTools 안 열어도 탐지 |
| 일반 Chrome (자동화 없음) | ❌ 정상 |

> **핵심**: Selenium은 내부적으로 **Chrome DevTools Protocol(CDP)** 로 브라우저를 제어한다.  
> devtools-detector는 console/log/창 크기 등 휴리스틱으로 "디버거 연결됨"을 감지 → **자동화 = DevTools** 로 본다.

그래서 `start_chrome.bat` (9222 attach) 모드는 **키이스케이프에서 사용 불가**.

---

### 7.2 우회 전략 — 3단계 방어

```mermaid
flowchart TB
    subgraph L1["1층: undetected-chromedriver"]
        UC[ChromeDriver 흔적 패치]
        UC2[navigator.webdriver 등 숨김]
    end

    subgraph L2["2층: CDN 차단 (CDP Network)"]
        BL[devtools-detector.min.js 다운로드 차단]
    end

    subgraph L3["3층: JS 선제 주입 (CDP Page)"]
        STUB[window.devtoolsDetector = noop stub]
        HTML[innerHTML setter 패치]
    end

    L1 --> L2 --> L3 --> OK[정상 페이지 렌더링]
```

구현: `keyescape_bypass.py` → `apply_keyescape_bypass(driver)`  
**반드시 `driver.get()` 이전**에 호출 (`main.py` → `open_keyescape()`).

---

### 7.3 1층 — undetected-chromedriver

`browser.py` → `_create_stealth_driver()`:

- 일반 ChromeDriver 대신 `undetected_chromedriver.Chrome` 사용
- `config.USE_UNDETECTED = True` (필수)
- 프로젝트 전용 프로필: `chrome_profile/` (쿠키·세션 유지)
- `config.CHROME_VERSION_MAIN` — Chrome/Chromedriver 버전 불일치 방지

---

### 7.4 2층 — CDN 요청 차단

```python
driver.execute_cdp_cmd("Network.enable", {})
driver.execute_cdp_cmd("Network.setBlockedURLs", {
    "urls": [
        "*devtools-detector*",
        "*cdnjs.cloudflare.com/ajax/libs/devtools-detector/*",
    ]
})
```

**동작 원리:**

```
브라우저가 devtools-detector.min.js 요청
        ↓
CDP Network.setBlockedURLs 가 URL 패턴 매칭
        ↓
요청 자체가 취소됨 (스크립트 never loaded)
        ↓
사이트 inline JS의 devtoolsDetector.launch() 호출 시
        ↓
3층 stub이 이미 깔려 있으므로 무력화
```

> CDN 차단만으로는 부족할 수 있다 — inline `<script>`가 `devtoolsDetector`를 바로 참조하기 때문.  
> 그래서 3층 **선제 stub** 이 반드시 필요하다.

---

### 7.5 3층-A — devtoolsDetector stub (가장 중요)

```python
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": DEVTOOLS_STUB_SCRIPT
})
```

`Page.addScriptToEvaluateOnNewDocument` 는 **모든 새 document(페이지/iframe) 로드 시,  
어떤 페이지 JS보다 먼저** 스크립트를 실행한다.

주입되는 stub:

```javascript
Object.defineProperty(window, "devtoolsDetector", {
  get: () => ({
    addListener: () => {},      // 리스너 등록해도 아무 일 없음
    launch: () => {},           // 탐지 시작 안 함
    stop: () => {},
    isLaunch: () => false,      // "실행 중 아님"
    setDetectDelay: () => {},
  }),
  set: () => {},               // 덮어쓰기 방지
});
```

**사이트 코드 vs 우리 stub — 타임라인:**

```
시간 →
─────────────────────────────────────────────────────────
[1] addScriptToEvaluateOnNewDocument stub 설치
[2] HTML 파싱 시작
[3] devtools-detector CDN 요청 → (2층에서 차단됨)
[4] inline script 실행:
      devtoolsDetector.addListener(...)  → noop, OK
      devtoolsDetector.launch()          → noop, OK
[5] 정상 페이지 표시 ✅
─────────────────────────────────────────────────────────
```

stub 없이 CDN만 차단하면:

```
[4] inline script:
      devtoolsDetector.addListener(...)
      → ReferenceError 또는 undefined (환경에 따라)
      → 또는 다른 경로로 탐지 발동
```

---

### 7.6 3층-B — innerHTML setter 패치 (2차 방어)

일부 경로(F12 단축키 등)에서는 inline script가 **직접** `blockDevTools()`를 호출한다:

```javascript
document.body.innerHTML = '...개발자 도구 사용이 금지...';
```

stub만으로 막지 못하는 경우를 대비해 **DOM 쓰기 자체를 가로챔**:

```javascript
const origSet = Element.prototype.innerHTML.set;
Object.defineProperty(Element.prototype, "innerHTML", {
  set: function(value) {
    if (typeof value === "string" && value.includes("개발자 도구 사용이 금지")) {
      return;  // 차단 HTML 무시
    }
    return origSet.call(this, value);
  }
});
```

```mermaid
flowchart LR
    A[blockDevTools 호출] --> B["body.innerHTML = '금지...'"]
    B --> C{setter 패치}
    C -->|금지 문구 포함| D[무시 — 페이지 유지]
    C -->|일반 HTML| E[정상 반영]
```

---

### 7.7 우회 전 vs 후 비교

| | 우회 없음 | 우회 적용 |
|---|----------|----------|
| Selenium 접속 | 검은 화면 + "개발자 도구 금지" | 정상 예약 UI |
| attach (9222) | 즉시 차단 | attach 자체 비권장 |
| F12 | 차단 | stub/패치로 완화 (사이트 키보드 hook은 별도) |
| 매크로 실행 | 불가 | F9 → 전 단계 자동화 가능 |

---

### 7.8 attach 모드가 안 되는 이유 (정리)

```mermaid
flowchart TD
    A[start_chrome.bat] --> B["Chrome --remote-debugging-port=9222"]
    B --> C[Selenium debuggerAddress 연결]
    C --> D[CDP 디버그 세션 활성]
    D --> E[devtools-detector: isOpen=true]
    E --> F[blockDevTools — 검은 화면]
```

**profile + uc + bypass** 조합만 사용:

```
run.bat → uc.Chrome(user_data_dir=chrome_profile) → bypass → get(url) → OK
```

---

## 8. 기술 스택 & 설계 원칙

### 8.1 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 브라우저 자동화 | Selenium 4 + **undetected-chromedriver** (`requirements.txt`) |
| 설정 UI | **tkinter** (표준 라이브러리, pip 불필요) |
| 설정 저장 | `settings.json` + `ui/storage.py` |
| CDP | `execute_cdp_cmd` (Network, Page) |
| 핫키 | Windows `ctypes` + `GetAsyncKeyState` |
| 서버 시각 | `urllib` + HTTP `Date` 헤더 |
| 사이트 API | `keyescape_api.py` → `POST /controller/run_proc.php` |
| reCAPTCHA | Google reCAPTCHA v2 + Enter 키 우회 시도 |

#### pip 의존성 (`requirements.txt`)

```
selenium>=4.25.0
undetected-chromedriver>=3.5.5
```

`undetected-chromedriver`가 `requests`, `websockets` 등을 **간접 설치**하지만 애플리케이션 코드는 `urllib` 위주로 HTTP를 처리한다.

### 8.2 속도 최적화 원칙

- **고정 sleep 제거** — 조건 충족 즉시 다음 단계
- **WebDriverWait poll 0.02s** — AJAX/마스크 해제 즉시 감지
- **JS batch** — 폼 필드·체크박스 한 번에 입력
- **implicitly_wait(0)** — 매크로 중 find_element 10초 블로킹 방지

### 8.3 스레드 안전

```
hotkey daemon thread  → queue.put("macro")
main thread loop      → queue.get() → run_macro(driver)  ← Selenium OK
terminal Enter thread → queue.put("macro")               ← Selenium OK
```

Selenium WebDriver는 **스레드 세이프하지 않음** → 반드시 메인 스레드에서만 호출.

---

## 9. 설정 가이드 (settings.json + UI)

### 9.1 설정 로드 순서

```mermaid
flowchart LR
    A[config.py 기본값] --> B{settings.json 존재?}
    B -->|Yes| C[ui/storage.apply_saved_settings]
    B -->|No| D[기본값만 사용]
    C --> E[import config 완료]
    D --> E
```

1. `config.py`에 코드 기본값·헬퍼 함수 정의
2. 모듈 import 마지막에 `_load_user_settings()` → `settings.json` 덮어쓰기
3. UI(`ui/app_tk.py`)는 저장 시 `settings.json`만 갱신 (다음 `main.py` 실행부터 반영)

### 9.2 UI 탭별 설정 항목

| 탭 | 주요 키 |
|----|---------|
| 예약 | `zizum_num`, `theme_num`, `theme_info_num`, `reservation_name`, `reservation_phone`, `macro_day_offset`, `macro_time`, `macro_time_slots`, `macro_hotkey` |
| Chrome | `chrome_mode`, `use_undetected`, `chrome_version_main`, `chrome_binary`, `headless`, … |
| 매크로 | `macro_poll_interval`, `macro_alert_retry_max`, … |
| 서버 시각 | `auto_run_enabled`, `auto_run_at`, `server_time_sync_interval`, … |
| CAPTCHA | `captcha_timeout`, `recaptcha_wait_timeout`, … |
| 경로 | `output_dir`, `screenshot_dir` |
| UI | `skip_ui_on_run` |

전체 필드 정의: `ui/schema.py` (`SETTING_FIELDS`, 51개).

### 9.3 예시 (settings.json)

```json
{
  "zizum_num": 23,
  "theme_num": 69,
  "theme_info_num": 60,
  "macro_day_offset": 6,
  "macro_time": "18:55",
  "auto_run_enabled": true,
  "auto_run_at": "11:00"
}
```

템플릿: `settings.example.json` — 개인정보는 git에 커밋하지 않음.

### 9.4 config.py 직접 수정

UI에 없거나 기본값만 바꿀 때 `config.py`를 편집해도 된다.  
`settings.json`에 같은 키가 있으면 **JSON이 우선**한다.

`MACRO_TIME_SLOTS`는 비어 있으면 `config.refresh_macro_time_slots()` / `keyescape_api`로 실행 시 채운다.

---

## 10. 실행 방법

### 10.1 최초 설치

```powershell
cd F:\Workspace\Crawling\keyscape
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

### 10.2 일반 실행

```powershell
.\run.bat                      # 설정 UI → 저장 후 매크로
.\settings.bat                 # 설정 UI만
.\run.bat --no-ui              # UI 건너뛰기
.\run.bat --settings           # skip_ui_on_run 이어도 UI 표시
.\run.bat --once               # 접속만
.\run.bat --no-auto            # F9/Enter 수동만
.\run.bat --auto-at 11:00      # 자동 실행 시각 override
.\run.bat --show-server-time   # 서버 KST 확인
```

| 키 | 동작 |
|----|------|
| F9 | 매크로 실행 |
| ESC | 종료 |
| Enter (터미널) | 매크로 실행 (F9 폴백) |

### 10.3 설정 UI 단독 실행 (개발)

```powershell
.\.venv\Scripts\python.exe -m ui.app_tk --settings
```

---

## 11. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: selenium` | venv 미설치 | `pip install -r requirements.txt` |
| 설정 창 안 뜸 | tkinter 미포함 Python | `python -m tkinter` 확인, python.org 재설치(tcl/tk) |
| "개발자 도구 금지" 검은 화면 | bypass 미적용 / attach 모드 | `profile` + `USE_UNDETECTED=True`, `chrome_profile/` 삭제 후 재실행 |
| F9 무반응 | 포커스/권한 | 터미널 Enter 사용 (이미 폴백 구현됨) |
| ChromeDriver 버전 오류 | Chrome 업데이트 | 설정 UI 또는 `CHROME_VERSION_MAIN` 수정 |
| reCAPTCHA 실패 | Google bot 판별 | `CAPTCHA_ENTER_RETRY` 증가, headless 끄기 |
| 예약 날짜 없음 | 아직 오픈 전 / offset 오류 | `MACRO_DAY_OFFSET`, 서버 SYSDATE 확인 |
| 자동 실행 시각 어긋남 | PC 시계 drift | `SERVER_TIME_PRE_SYNC_SEC` 구간 재동기화 확인 |
| settings 반영 안 됨 | 저장 안 함 / 키 오타 | `settings.json` 저장 후 재실행, `settings.example.json` 참고 |

### bypass 검증

```python
body = driver.find_element(By.TAG_NAME, "body").text
assert "개발자 도구 사용이 금지" not in body
```

---

## 부록: 데이터 흐름 (예약 제출)

```mermaid
sequenceDiagram
    participant M as macro.py
    participant B as Browser
    participant API as run_proc.php
    participant R3 as reservation3.php

    M->>B: JS 폼 입력 + 동의 체크
    M->>B: reCAPTCHA Enter
    M->>B: button.submit 클릭
    B->>API: POST FormData (t=ins_rev, …)
    API-->>B: JSON { status, data: { num, ck_code } }
    B->>R3: location.href = reservation3.php?…
    M->>M: URL 폴링 → 완료
```

---

*문서 버전: 2026-06-24 — settings UI, settings.json, keyescape_api 반영*
