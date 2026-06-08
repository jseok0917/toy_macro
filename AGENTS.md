# Keyscape Selenium Macro — Agent Guide

## Project summary

Python Selenium macro for [keyescape.com](https://www.keyescape.com) room escape reservations. Uses **undetected-chromedriver**, **devtools bypass**, and **F9 hotkey** trigger.

## Run

```powershell
.\run.bat
```

## Key files

- `macro.py` — edit macro logic here
- `config.py` — URL, `MACRO_DAY_OFFSET`, `MACRO_TIME`
- `keyescape_bypass.py` — required before navigation
- `hotkey.py` — F9 / ESC / Enter fallback

## Cursor skills (project)

| Skill | Use when |
|-------|----------|
| `keyescape-reservation-macro` | Adding/changing booking steps |
| `keyescape-devtools-bypass` | Devtools block / black screen |
| `keyescape-run-debug` | run.bat, Chrome, F9 issues |
| `keyescape-api` | HTTP API for schedules/slots |

## Rules

See `.cursor/rules/` — `project-overview.mdc` always applies.

## Constraints

- Windows + PowerShell: `.\run.bat`, not `run.bat`
- Do not use attach/debug Chrome mode on keyescape
- Keep Selenium on main thread only
