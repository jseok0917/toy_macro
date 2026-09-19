# Keyscape 예약 매크로

## settings.json 설정 항목

UI(`settings.bat` / `run.bat`)에서 저장하는 값입니다. `config.py` 기본값 위에 덮어씁니다.  
형식 예시는 [`settings.example.json`](settings.example.json)을 참고하세요.

### 예약

| 키 | 형식 | 설명 |
|----|------|------|
| `zizum_num` | 정수 | 키이스케이프 **지점** 번호 (`zizum_num` URL 파라미터) |
| `theme_num` | 정수 | **테마** 번호 (`theme_num`) |
| `theme_info_num` | 정수 | **테마 상세** 번호 (`theme_info_num`, 달력·시간 API용) |
| `reservation_name` | 문자열 | 예약 2단계에 입력할 **예약자 이름** |
| `reservation_phone` | 문자열 | 연락처 **뒤 8자리** (`2736-3607` 또는 `27363607`, 010은 사이트 고정) |
| `reservation_base_url` | URL | 예약 1단계 페이지 주소 (보통 `reservation1.php`) |
| `macro_day_offset` | 정수 (≥0) | 예약 날짜 = **서버 SYSDATE + N일** |
| `macro_time` | `HH:MM` | 우선 예약할 **시간 슬롯** |
| `macro_time_fallback_enabled` | true/false | `true`면 `macro_time` 마감 시 **같은 날 더 늦은 슬롯**을 순서대로 시도 |
| `macro_time_slots` | 시간 배열 | 슬롯 목록. **비우면** 실행 시 API로 조회. 직접 넣을 때 `09:45, 10:40` 형식 |
| `macro_hotkey` | 문자열 | 수동 매크로 핫키 이름 (기본 `f9`, Windows 폴링) |

### 매크로

| 키 | 형식 | 설명 |
|----|------|------|
| `macro_step_delay` | 초 (≥0) | 단계 사이 **고정 sleep** (0이면 응답 즉시 다음 단계) |
| `macro_wait_timeout` | 초 (≥0) | 요소 대기 **최대 시간** (짧게 두면 빠른 폴링) |
| `macro_poll_interval` | 초 (≥0) | 조건 폴링 **간격** (예: 0.02) |
| `macro_time_click_timeout` | 초 (≥0) | 시간 슬롯 **클릭 시도** 제한 (마감 시 다음 슬롯으로 넘김) |
| `macro_time_list_wait_timeout` | 초 (≥0) | 날짜 클릭 후 **시간 목록 AJAX** 응답 대기 |
| `macro_time_group_retry_max` | 정수 (≥0) | (설정 시간→이후 시간 전체 스캔) **그룹 재시도** 횟수 |
| `macro_time_group_retry_delay` | 초 (≥0) | 시간 그룹 재시도 **간격** |
| `macro_alert_retry_delay` | 초 (≥0) | alert/목록 재시도 **전 대기** |
| `macro_alert_retry_max` | 정수 (≥0) | 날짜·시간 목록 **재시도 최대** 횟수 |
| `macro_mask_timeout` | 초 (≥0) | 로딩 **마스크(`#mask`)** 사라질 때까지 대기 |
| `macro_submit_timeout` | 초 (≥0) | 예약 **제출 후** 완료 페이지·응답 대기 |

### 서버 시각

| 키 | 형식 | 설명 |
|----|------|------|
| `auto_run_enabled` | true/false | **서버 KST 기준** 지정 시각에 매크로 자동 실행 |
| `auto_run_at` | `HH:MM` | 자동 실행 **시각** (서버 시각, 예: `11:00`) |
| `auto_run_min_delay_ms` | 0~50 | 해당 시각 **직후 최소 지연(ms)** — 0이면 정각, 동시 클릭 완화용 |
| `server_time_sync_interval` | 초 (≥1) | HTTP `Date`로 **서버 시각 재동기화** 주기 |
| `server_time_pre_sync_sec` | 초 (≥0) | 자동 실행 **N초 전부터** 촘촘히 재동기화 |
| `server_time_final_spin_sec` | 초 (≥0) | 마지막 N초는 HTTP sync 없이 **ms 단위 폴링** |
| `server_time_stale_max_sec` | 초 (≥0) | HTTP Date가 로컬 추정보다 느릴 때 **보정 상한** |
| `server_time_max_forward_sec` | 초 (≥0) | sync 1회당 시계를 **앞당기는 상한** |
| `server_time_timeout` | 초 (≥1) | 서버 시각 HTTP 조회 **타임아웃** |

### CAPTCHA

| 키 | 형식 | 설명 |
|----|------|------|
| `captcha_timeout` | 초 (≥0) | CAPTCHA 관련 요소 **대기 시간** |
| `recaptcha_wait_timeout` | 초 (≥0) | 「로봇이 아닙니다」 **수동 완료** 최대 대기 |
| `captcha_wait_before_enter` | 초 (≥0) | reCAPTCHA에 **Enter 보내기 전** 대기 |
| `captcha_settle_wait` | 초 (≥0) | CAPTCHA UI **안정화** 대기 |
| `captcha_enter_retry` | 정수 (≥0) | Enter 키 **재시도 횟수** |

> Chrome·폴더 경로 등은 `settings.json`에 없으며 **`config.py`**에서 관리합니다.

---

[keyescape.com](https://www.keyescape.com) 방탈출 예약 페이지를 **undetected-chromedriver + Selenium**으로 자동화하는 Windows용 매크로입니다.  
**F9** 수동 실행, **서버 KST 시각** 자동 실행, **tkinter 설정 UI**를 지원합니다.

---

## 요구 사항

| 항목 | 설명 |
|------|------|
| OS | Windows 10/11 |
| Python | 3.10 이상 권장 |
| Google Chrome | 최신 버전 설치 |
| tkinter | 설정 UI용 — [python.org](https://www.python.org/downloads/) 설치 시 **tcl/tk** 옵션 포함 (기본 체크) |

---

## 설치

PowerShell에서 프로젝트 폴더로 이동한 뒤:

```powershell
cd F:\Workspace\Crawling\keyscape

python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

### 의존성 요약

**`pip install` 대상** (`requirements.txt`):

| 패키지 | 용도 |
|--------|------|
| `selenium` | Chrome 제어, CDP 우회 주입 |
| `undetected-chromedriver` | Selenium/ChromeDriver 탐지 우회 |

**표준 라이브러리** (별도 설치 불필요):

| 모듈 | 용도 |
|------|------|
| `tkinter` | 설정 UI (`ui/app_tk.py`) |
| `urllib` | 서버 시각 동기화, 키이스케이프 API |
| `ctypes` | F9 / ESC 전역 핫키 |

> `undetected-chromedriver` 설치 시 `requests`, `websockets` 등이 **간접 의존성**으로 함께 설치됩니다. 프로젝트 코드에서 직접 import 하지는 않습니다.

---

## 실행 방법

### 기본 (설정 UI → 매크로)

```powershell
.\run.bat
```

1. **설정 창**이 열립니다 (`ui/app_tk.py`).
2. **저장 후 실행** → `settings.json` 저장 → Chrome 실행 → 예약 페이지 접속.
3. **F9** / 터미널 **Enter** / **서버 시각 자동 실행** 대기.

### 설정만 열기

```powershell
.\settings.bat
```

### 자주 쓰는 옵션

```powershell
.\run.bat --no-ui          # 설정 UI 건너뛰고 바로 실행
.\run.bat --settings       # skip 설정이 있어도 UI 강제 표시
.\run.bat --once           # 접속만 하고 F9 대기 없이 종료
.\run.bat --no-auto        # 자동 실행 끄기 (F9/Enter만)
.\run.bat --auto-at 11:00  # 자동 실행 시각 덮어쓰기 (서버 KST)
.\run.bat --show-server-time   # 서버 KST 출력 후 종료
```

| 키 | 동작 |
|----|------|
| **F9** | 매크로 실행 |
| **ESC** | 종료 |
| **Enter** (터미널 포커스) | 매크로 실행 (F9 폴백) |

> PowerShell에서는 `run.bat` ❌ → **`.\run.bat`** ✅  
> 터미널을 닫으면 F9 핫키 루프가 종료됩니다 (Chrome 창은 유지될 수 있음).

---

## 설정

### settings.json (권장)

UI에서 저장한 값은 프로젝트 루트의 **`settings.json`**에 기록됩니다.  
개인정보(이름·전화번호)가 포함되므로 git에 올리지 않습니다.

- 예시: `settings.example.json` 복사 후 수정
- `config.py`의 기본값 위에 **덮어씀**
- UI 탭: **예약 · 매크로 · 서버 시각 · CAPTCHA**
- 항목 설명: 이 문서 **맨 위 [settings.json 설정 항목](#settingsjson-설정-항목)** 참고

### config.py

코드 기본값·함수(`build_reservation_url`, `get_macro_time_candidates` 등)가 정의되어 있습니다.  
UI에 없는 값만 코드에서 직접 수정하면 됩니다.

---

## 프로젝트 구조

```
keyscape/
├── run.bat              # 매크로 실행 (설정 UI 포함)
├── settings.bat         # 설정 UI만
├── main.py              # CLI 진입점, Chrome 세션, 핫키 루프
├── config.py            # 기본 설정 + settings.json 로드
├── macro.py             # 예약 매크로 본체
├── browser.py           # Chrome 생성
├── keyescape_bypass.py  # devtools-detector 우회
├── keyescape_api.py     # 예약 API (시간 슬롯 조회 등)
├── hotkey.py            # F9 / ESC / 자동 실행
├── server_time.py       # 서버 KST 동기화
├── ui/
│   ├── app_tk.py        # 설정 UI
│   ├── schema.py        # 설정 필드 정의
│   └── storage.py       # settings.json I/O
├── settings.json        # 사용자 설정 (gitignore)
├── chrome_profile/      # 전용 Chrome 프로필
└── requirements.txt
```

---

## 제약 · 주의

- **headless / attach(`start_chrome.bat`)** 는 키이스케이프 devtools 탐지에 걸릴 수 있음 → **`profile` + `USE_UNDETECTED=True`** 사용.
- Selenium 호출은 **메인 스레드에서만** (핫키 콜백에서 직접 호출 금지).
- Chrome·매크로 문제 시: `chrome_profile` 폴더 삭제 후 `.\run.bat` 재실행.

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: selenium` | venv 활성화 후 `pip install -r requirements.txt` |
| 설정 창이 안 뜸 | `python -m tkinter` 로 tkinter 설치 여부 확인 |
| "개발자 도구 금지" 검은 화면 | `chrome_profile` 삭제, `profile` 모드·`USE_UNDETECTED=True` 확인 |
| F9 무반응 | 터미널에 포커스 두고 **Enter** 사용 |
| ChromeDriver 버전 오류 | 설정 UI 또는 `config.py`에서 `CHROME_VERSION_MAIN` 수정 |

---

## 문서

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — 아키텍처, 매크로 흐름, bypass 상세, 모듈 의존 관계
