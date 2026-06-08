---
name: keyescape-api
description: Queries keyescape.com reservation backend API (run_proc.php)—themes, calendar, time slots without browser. Use when analyzing schedules, doing SYSDATE+offset logic, or replacing UI clicks with HTTP requests.
---

# Keyescape API

Base: `POST https://www.keyescape.com/controller/run_proc.php`  
Content-Type: `application/x-www-form-urlencoded`  
Response: JSON

## Endpoints

### Theme list

```python
{"t": "get_theme_info_list", "zizum_num": "23"}
```

Returns `data[]` with `info_num`, `theme_num`, `doing`, `info_name`.

### Theme + calendar

```python
{"t": "get_theme_date", "num": "60"}  # theme_info_num
```

Returns theme details + `calendarData.days_in_month`, `first_day_of_month`.

### Month navigation

```python
{"t": "get_caledar_data", "year": "2026", "month": "06"}
```

### Time slots

```python
{
  "t": "get_theme_time",
  "date": "2026-06-12",
  "zizumNum": "23",
  "themeNum": "69",
  "endDay": "0",  # 1 if last bookable day
}
```

Returns `data[]` with `hh`, `mm`, `num`, `enable` (`Y`/`N`).

## Example (requests)

```python
import urllib.request, urllib.parse, json

def post(params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://www.keyescape.com/controller/run_proc.php", data=data
    )
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

slots = post({
    "t": "get_theme_time",
    "date": "2026-06-12",
    "zizumNum": "23",
    "themeNum": "69",
    "endDay": "0",
})
```

## Bookable window

From theme `doing` value:

```text
last_bookable = today + (doing - 1) days
```

## When to use API vs Selenium

| Use API | Use Selenium |
|---------|--------------|
| Check slot availability | Click UI / submit forms |
| Validate date in range | Pass client-side checks |
| Batch monitoring | reservation2+ user input |

Server may reject out-of-range dates even if UI is bypassed.
