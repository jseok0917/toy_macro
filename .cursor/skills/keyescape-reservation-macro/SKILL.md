---
name: keyescape-reservation-macro
description: Implements and extends Keyescape (keyescape.com) reservation Selenium macros—date/time selection, F9 hotkey flow, reservation1→2 steps. Use when adding macro steps, changing booking date/time, or working on macro.py, reservation flow, or 예약 매크로.
---

# Keyescape Reservation Macro

## Quick reference

| Setting | Location |
|---------|----------|
| Target URL | `config.py` / `main.py` `--url` |
| Date offset (SYSDATE+N) | `config.MACRO_DAY_OFFSET` |
| Time slot | `config.MACRO_TIME` (e.g. `09:20`) |
| Macro body | `macro.py` → `run_macro()` |

## Standard F9 flow (reservation1)

1. Click `.selDate.available[data-date='{today+N}']`
2. Wait `#datepicker.timepicker .timeList`
3. Click label with enabled `input.selThemeTimeNum` + span starting with `{MACRO_TIME}`
4. Wait `#reservInfo` visible
5. Click `.btn_next_step` → wait `reservation2.php` in URL

## Date availability (site JS)

```text
available if: today <= date <= today + (doing - 1)
```

`doing` comes from theme option `data-doing` (DB). Example: `doing=7` → today through today+6.

## Adding macro steps

1. Add helpers as `_click_*` / `_fill_*` private functions in `macro.py`
2. Call from `run_macro()` in order
3. Use `WebDriverWait(driver, config.MACRO_WAIT_TIMEOUT)` — avoid relying on long `implicitly_wait`
4. Guard with `_running` lock (already in `run_macro`)

## AJAX loading

- Loading mask: `#mask` — wait until class contains `hide` or not displayed
- After date click, calendar becomes `#datepicker.timepicker`

## reservation2 extension

- Form submits via hidden fields: `zizumNum`, `themeNum`, `themeInfoNum`, `revDays`, `themeTimeNum`
- Inspect reservation2 page before automating; keep step2 in separate function e.g. `_fill_reservation2()`

## Do not

- Use `attach` / `start_chrome.bat` for keyescape (devtools detection)
- Call Selenium from hotkey callback threads
- Hardcode dates — use `MACRO_DAY_OFFSET`
