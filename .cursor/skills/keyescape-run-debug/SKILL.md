---
name: keyescape-run-debug
description: Runs and debugs the Keyscape macro on Windows—run.bat, venv, Chrome not opening, F9 not working, selenium errors. Use when run.bat fails, Chrome won't start, ModuleNotFoundError, or hotkey issues.
---

# Run & Debug (Windows)

## Correct launch

```powershell
cd F:\Workspace\Crawling\keyscape
.\run.bat
```

Not `run.bat` (PowerShell requires `.\`).

## venv / ModuleNotFoundError

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

`run.bat` auto-uses `.venv\Scripts\python.exe` if present.

## Chrome not visible / closes immediately

| Symptom | Check |
|---------|--------|
| Script exits instantly | Use `.\run.bat` without `--once`; terminal must stay open for F9 |
| No browser window | Run `.\.venv\Scripts\python.exe main.py --once` and read stderr |
| ChromeDriver version mismatch | Set `config.CHROME_VERSION_MAIN` to installed Chrome major (e.g. 148) |
| Profile lock | Close all Chrome; delete `chrome_profile/` if corrupted |

## Test Chrome only

```powershell
.\.venv\Scripts\python.exe main.py --once
```

Expect: `[Chrome]`, `[Bypass]`, `[OK] 접속:` lines.

## F9 not working

1. Terminal must show `[Ready]` and `[Hotkey] F9 = 매크로...`
2. Try **Enter in terminal** (fallback)
3. Laptop: **Fn+F9**
4. Do not close terminal while waiting

## CLI flags

| Flag | Effect |
|------|--------|
| (default) | Open URL + F9 wait loop |
| `--once` | Open URL, exit (no F9) |
| `--close` | Quit Chrome on exit |
| `--current` | Attach mode (not for keyescape) |

## Common errors

- `session not created ... Chrome version` → fix `CHROME_VERSION_MAIN` in `config.py`
- `devtools 차단` → delete `chrome_profile`, ensure bypass + uc mode
- `invalid session id` → browser closed mid-run; rerun `.\run.bat`

## After code changes

No reinstall needed unless `requirements.txt` changed. Restart `.\run.bat` to pick up Python changes.
