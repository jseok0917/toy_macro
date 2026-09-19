"""키이스케이프 매크로 설정 UI (tkinter)."""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import config
from ui.schema import FIELDS_BY_TAB, SETTING_FIELDS, TAB_ORDER, SettingField
from ui.storage import load_effective_settings, read_settings_file, save_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="키이스케이프 매크로 설정")
    parser.add_argument("--no-ui", action="store_true", help="설정 창 없이 종료")
    parser.add_argument(
        "--settings",
        action="store_true",
        help="설정 창 강제 표시 (skip_ui_on_run 무시)",
    )
    return parser.parse_args()


def _should_skip_ui(*, force_settings: bool) -> bool:
    if force_settings:
        return False
    return bool(read_settings_file().get("skip_ui_on_run"))


_LABEL_WIDTH = 36
_ENTRY_WIDTH = 42
_SCROLL_HEIGHT = 420
_WINDOW_PAD = 24


class _ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, height=_SCROLL_HEIGHT)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)
        self.body.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._window_id = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind("<Configure>", self._on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
        self._canvas = canvas

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._canvas.itemconfig(self._window_id, width=event.width)

    def destroy(self) -> None:
        self._canvas.unbind_all("<MouseWheel>")
        super().destroy()


class SettingsApp(tk.Tk):
    def __init__(self, *, standalone: bool) -> None:
        super().__init__()
        self._standalone = standalone
        self._vars: dict[str, tk.Variable] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._time_combo: ttk.Combobox | None = None
        self._multiline: dict[str, scrolledtext.ScrolledText] = {}

        self.title("키이스케이프 매크로 설정")
        self.minsize(720, 560)
        self._configure_style()

        settings = load_effective_settings()
        self._init_vars(settings)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

    def _configure_style(self) -> None:
        try:
            self.option_add("*Font", ("맑은 고딕", 10))
        except tk.TclError:
            pass

    def _init_vars(self, settings: dict) -> None:
        for field in SETTING_FIELDS:
            value = settings[field.key]
            if field.kind == "bool":
                self._vars[field.key] = tk.BooleanVar(value=bool(value))
            elif field.kind == "time_list":
                text = ", ".join(value) if value else ""
                self._vars[field.key] = tk.StringVar(value=text)
            else:
                self._vars[field.key] = tk.StringVar(value=str(value) if value is not None else "")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        for tab_name in TAB_ORDER:
            scroll = _ScrollFrame(notebook)
            notebook.add(scroll, text=tab_name)
            self._build_tab(scroll.body, tab_name)

        summary = ttk.Label(
            outer,
            text="저장 시 settings.json에 기록되며 다음 실행부터 적용됩니다.",
            foreground="#555555",
        )
        summary.pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(anchor="e", pady=(12, 0))

        if self._standalone:
            ttk.Button(buttons, text="저장", command=self._on_save).pack(side="left", padx=4)
            ttk.Button(buttons, text="닫기", command=self._on_close).pack(side="left", padx=4)
        else:
            ttk.Button(buttons, text="저장 후 실행", command=self._on_save).pack(side="left", padx=4)
            ttk.Button(buttons, text="건너뛰기", command=self._on_skip).pack(side="left", padx=4)

    def _fit_window_size(self) -> None:
        self.update_idletasks()
        w = self.winfo_reqwidth() + _WINDOW_PAD
        h = self.winfo_reqheight() + _WINDOW_PAD
        self.minsize(w, h)
        self.geometry(f"{w}x{h}")

    def _build_tab(self, parent: ttk.Frame, tab_name: str) -> None:
        pad = {"padx": 10, "pady": 4}
        for row, field in enumerate(FIELDS_BY_TAB[tab_name]):
            self._add_field(parent, field, row, pad)

        if tab_name == "예약":
            self._url_label = ttk.Label(parent, text="", wraplength=560, foreground="#333333")
            self._url_label.grid(row=len(FIELDS_BY_TAB[tab_name]), column=0, columnspan=2, sticky="w", **pad)
            self._update_url_preview()
            for key in ("zizum_num", "theme_num", "theme_info_num"):
                self._vars[key].trace_add(
                    "write",
                    lambda *_: (self._update_url_preview(), self._refresh_time_slots()),
                )
            self._refresh_time_slots()

    def _add_field(self, parent: ttk.Frame, field: SettingField, row: int, pad: dict) -> None:
        ttk.Label(parent, text=field.label, width=_LABEL_WIDTH).grid(
            row=row, column=0, sticky="nw", **pad
        )

        if field.kind == "bool":
            widget = ttk.Checkbutton(parent, variable=self._vars[field.key])
            widget.grid(row=row, column=1, sticky="w", **pad)
            self._widgets[field.key] = widget
            return

        if field.kind == "choice":
            widget = ttk.Combobox(
                parent,
                textvariable=self._vars[field.key],
                values=list(field.choices),
                width=_ENTRY_WIDTH,
                state="readonly",
            )
            widget.grid(row=row, column=1, sticky="w", **pad)
            self._widgets[field.key] = widget
            return

        if field.widget == "macro_time":
            widget = ttk.Combobox(parent, textvariable=self._vars[field.key], width=_ENTRY_WIDTH)
            widget.grid(row=row, column=1, sticky="w", **pad)
            self._time_combo = widget
            self._widgets[field.key] = widget
            return

        if field.widget == "multiline":
            widget = scrolledtext.ScrolledText(parent, width=_ENTRY_WIDTH, height=4, wrap="word")
            widget.insert("1.0", self._vars[field.key].get())
            widget.grid(row=row, column=1, sticky="w", **pad)
            self._multiline[field.key] = widget
            return

        widget = ttk.Entry(parent, textvariable=self._vars[field.key], width=_ENTRY_WIDTH)
        widget.grid(row=row, column=1, sticky="w", **pad)
        self._widgets[field.key] = widget

    def _update_url_preview(self) -> None:
        try:
            url = config.build_reservation_url(
                zizum_num=int(self._vars["zizum_num"].get()),
                theme_num=int(self._vars["theme_num"].get()),
                theme_info_num=int(self._vars["theme_info_num"].get()),
            )
        except ValueError:
            url = "(지점/테마 번호를 확인하세요)"
        self._url_label.configure(text=f"URL 미리보기:\n{url}")

    def _refresh_time_slots(self) -> None:
        if self._time_combo is None:
            return
        try:
            zizum = int(self._vars["zizum_num"].get())
            theme = int(self._vars["theme_num"].get())
        except ValueError:
            return
        try:
            slots = config.refresh_macro_time_slots(zizum_num=zizum, theme_num=theme)
            self._time_combo.configure(values=[s.time for s in slots])
        except Exception:
            manual = self._vars.get("macro_time_slots")
            if manual is not None and manual.get().strip():
                values = [part.strip() for part in manual.get().replace("\n", ",").split(",") if part.strip()]
                self._time_combo.configure(values=values)

    def _collect(self) -> dict:
        data: dict = {}
        for field in SETTING_FIELDS:
            if field.key in self._multiline:
                data[field.key] = self._multiline[field.key].get("1.0", "end").strip()
            elif field.kind == "bool":
                data[field.key] = self._vars[field.key].get()
            else:
                data[field.key] = self._vars[field.key].get()
        return data

    def _on_save(self) -> None:
        try:
            save_settings(self._collect())
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc), parent=self)
            return

        if self._standalone:
            messagebox.showinfo("저장 완료", "settings.json에 저장했습니다.", parent=self)
        self.destroy()

    def _on_skip(self) -> None:
        self.destroy()

    def _on_close(self) -> None:
        self.destroy()


def main() -> int:
    args = _parse_args()
    if args.no_ui:
        return 0
    if _should_skip_ui(force_settings=args.settings):
        return 0

    app = SettingsApp(standalone=args.settings)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
