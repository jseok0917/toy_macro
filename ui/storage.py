"""settings.json 읽기/쓰기 및 config 반영."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ui.schema import SETTING_FIELDS, SETTING_KEYS, SettingField

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"


def read_settings_file() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    with SETTINGS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("settings.json 형식 오류: 최상위가 객체여야 합니다.")
    return data


def _serialize_value(field: SettingField, value: Any) -> Any:
    if field.kind == "path":
        return str(value)
    if field.kind == "time_list":
        if not value:
            return []
        return [normalize_hhmm(str(v)) for v in value]
    if field.kind == "bool":
        return bool(value)
    return value


def _read_config_value(field: SettingField) -> Any:
    import config

    if field.attr is None:
        return False

    value = getattr(config, field.attr)
    if field.kind == "path":
        return str(value)
    if field.kind == "time_list":
        return list(value) if value else []
    return value


def settings_from_config() -> dict[str, Any]:
    return {field.key: _read_config_value(field) for field in SETTING_FIELDS}


def load_effective_settings() -> dict[str, Any]:
    base = settings_from_config()
    saved = read_settings_file()
    for key in SETTING_KEYS:
        if key in saved:
            base[key] = saved[key]
    return base


def normalize_hhmm(value: str) -> str:
    hour, minute = value.strip().split(":", 1)
    return f"{int(hour):02d}:{int(minute):02d}"


def _validate_hhmm(value: str, field_label: str) -> str:
    raw = str(value).strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", raw):
        raise ValueError(f"{field_label} 형식 오류: {raw!r} (HH:MM)")
    return normalize_hhmm(raw)


def _parse_time_list(raw: Any, field_label: str) -> list[str]:
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, list):
        items = [str(v).strip() for v in raw if str(v).strip()]
    else:
        text = str(raw).replace("\n", ",")
        items = [part.strip() for part in text.split(",") if part.strip()]
    return [_validate_hhmm(item, field_label) for item in items]


def _validate_numeric(
    value: Any,
    field: SettingField,
    *,
    as_float: bool,
) -> int | float:
    try:
        parsed = float(value) if as_float else int(value)
    except (TypeError, ValueError) as exc:
        kind = "숫자" if as_float else "정수"
        raise ValueError(f"{field.label}은(는) {kind}여야 합니다: {value!r}") from exc

    if field.min_value is not None and parsed < field.min_value:
        raise ValueError(f"{field.label}은(는) {field.min_value} 이상이어야 합니다.")
    if field.max_value is not None and parsed > field.max_value:
        raise ValueError(f"{field.label}은(는) {field.max_value} 이하여야 합니다.")
    return parsed


def _validate_field(field: SettingField, raw: Any) -> Any:
    if field.kind == "bool":
        return bool(raw)

    if field.kind == "int":
        return _validate_numeric(raw, field, as_float=False)

    if field.kind == "float":
        return _validate_numeric(raw, field, as_float=True)

    if field.kind == "hhmm":
        return _validate_hhmm(str(raw), field.label)

    if field.kind == "choice":
        value = str(raw).strip()
        if value not in field.choices:
            raise ValueError(f"{field.label}: {field.choices} 중 하나여야 합니다.")
        return value

    if field.kind == "path":
        text = str(raw).strip()
        if not text:
            raise ValueError(f"{field.label}을(를) 입력하세요.")
        return text

    if field.kind == "time_list":
        return _parse_time_list(raw, field.label)

    value = str(raw).strip()
    if field.key == "reservation_name" and not value:
        raise ValueError("예약자 이름을 입력하세요.")
    if field.key == "reservation_base_url" and not value:
        raise ValueError("예약 페이지 URL을 입력하세요.")
    if field.key == "macro_hotkey" and not value:
        raise ValueError("매크로 핫키를 입력하세요.")
    return value


def _validate_reservation_phone(phone: str) -> None:
    import config

    prev_name, prev_phone = config.RESERVATION_NAME, config.RESERVATION_PHONE
    try:
        config.RESERVATION_PHONE = phone
        config.get_reservation_phone_parts()
    finally:
        config.RESERVATION_NAME = prev_name
        config.RESERVATION_PHONE = prev_phone


def validate_settings(data: dict[str, Any]) -> dict[str, Any]:
    """UI 입력 검증 후 저장용 dict 반환."""
    validated: dict[str, Any] = {}
    for field in SETTING_FIELDS:
        if field.key not in data and field.attr is not None:
            raw = _read_config_value(field)
        else:
            raw = data.get(field.key)
        validated[field.key] = _validate_field(field, raw)

    _validate_reservation_phone(validated["reservation_phone"])
    return validated


def save_settings(data: dict[str, Any]) -> None:
    validated = validate_settings(data)
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _resolve_path(value: str) -> Path:
    import config

    path = Path(value)
    if not path.is_absolute():
        path = config.BASE_DIR / path
    return path


def _apply_value(field: SettingField, value: Any) -> None:
    import config

    if field.attr is None:
        return

    if field.kind == "path":
        setattr(config, field.attr, _resolve_path(str(value)))
    elif field.kind in ("int", "float", "bool", "str", "choice", "hhmm"):
        setattr(config, field.attr, value)
    elif field.kind == "time_list":
        setattr(config, field.attr, list(value))


def apply_saved_settings() -> None:
    """config import 시 settings.json 값을 모듈 변수에 반영."""
    saved = read_settings_file()
    if not saved:
        return

    for field in SETTING_FIELDS:
        if field.key not in saved:
            continue
        raw = saved[field.key]
        try:
            parsed = _validate_field(field, raw)
        except ValueError:
            continue
        _apply_value(field, parsed)
