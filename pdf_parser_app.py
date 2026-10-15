import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter

APP_TITLE = "PDF Parser"
ERROR_COLOR = ("#c0392b", "#ff6b6b")
OK_COLOR = ("#1e8449", "#58d68d")
MUTED_COLOR = ("gray35", "gray65")

THEMES = {"Светлая": "light", "Тёмная": "dark", "Система": "system"}


def open_in_system(path: str) -> None:
    """Открыть файл/папку программой по умолчанию."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry("1120x740")
        self.minsize(960, 620)

        # --- состояние ---
        self.src_path: str | None = None
        self.doc: fitz.Document | None = None
        self.total = 0
        self.out_dir: str = ""
        self.last_output: str | None = None
        self.view_mode = "Новый файл" 
        self.cur = 0  
        self._render_job = None
        self._name_manual = False

        self._blank = None

        self.var_start = tk.StringVar(value="1")
        self.var_end = tk.StringVar(value="1")
        self.var_name = tk.StringVar(value="")
        self.var_start.trace_add("write", self._on_range_change)
        self.var_end.trace_add("write", self._on_range_change)

        self._blank = ctk.CTkImage(
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        self._build_ui()
        self._update_controls()

        self.bind("<Left>", lambda e: self._key_nav(-1))
        self.bind("<Right>", lambda e: self._key_nav(1))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== левая панель =====
        side = ctk.CTkScrollableFrame(self, width=330, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            side, text="PDF Parser", font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(18, 0))
        ctk.CTkLabel(
            side,
            text="Создайте новый PDF из нужных страниц",
            text_color=MUTED_COLOR,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))

        # --- 1. исходный файл ---
        card1 = self._card(side, 2, "1  Исходный файл")
        self.btn_open = ctk.CTkButton(
            card1, text="Выбрать PDF…", height=38, command=self.choose_file
        )
        self.btn_open.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 8))
        self.lbl_file = ctk.CTkLabel(
            card1, text="Файл не выбран", wraplength=270, justify="left",
            text_color=MUTED_COLOR,
        )
        self.lbl_file.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))

        # --- 2. диапазон ---
        card2 = self._card(side, 3, "2  Диапазон страниц")
        card2.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(card2, text="Начальная").grid(
            row=1, column=0, sticky="w", padx=14)
        ctk.CTkLabel(card2, text="Конечная").grid(
            row=1, column=1, sticky="w", padx=(6, 14))
        self.ent_start = ctk.CTkEntry(card2, textvariable=self.var_start, height=36)
        self.ent_start.grid(row=2, column=0, sticky="ew", padx=(14, 6), pady=(2, 4))
        self.ent_end = ctk.CTkEntry(card2, textvariable=self.var_end, height=36)
        self.ent_end.grid(row=2, column=1, sticky="ew", padx=(6, 14), pady=(2, 4))
        self.lbl_range = ctk.CTkLabel(
            card2, text="", wraplength=270, justify="left", text_color=MUTED_COLOR
        )
        self.lbl_range.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 12))

        # --- 3. новый файл ---
        card3 = self._card(side, 4, "3  Новый файл")
        ctk.CTkLabel(card3, text="Название файла").grid(
            row=1, column=0, sticky="w", padx=14)
        self.ent_name = ctk.CTkEntry(card3, textvariable=self.var_name, height=36)
        self.ent_name.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 8))
        self.ent_name.bind("<Key>", lambda e: setattr(self, "_name_manual", True))
        self.btn_dir = ctk.CTkButton(
            card3, text="Папка сохранения…", height=32, fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self.choose_dir,
        )
        self.btn_dir.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 4))
        self.lbl_dir = ctk.CTkLabel(
            card3, text="", wraplength=270, justify="left",
            text_color=MUTED_COLOR, font=ctk.CTkFont(size=11),
        )
        self.lbl_dir.grid(row=4, column=0, sticky="w", padx=14, pady=(0, 12))

        # --- действия ---
        self.btn_create = ctk.CTkButton(
            side, text="Создать PDF", height=46,
            font=ctk.CTkFont(size=15, weight="bold"), command=self.create_pdf,
        )
        self.btn_create.grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 6))
        self.btn_show = ctk.CTkButton(
            side, text="Открыть результат", height=34, fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self.open_result, state="disabled",
        )
        self.btn_show.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 6))
        self.lbl_status = ctk.CTkLabel(
            side, text="", wraplength=290, justify="left")
        self.lbl_status.grid(row=7, column=0, sticky="w", padx=16, pady=(0, 10))

        # --- тема ---
        theme_box = ctk.CTkFrame(side, fg_color="transparent")
        theme_box.grid(row=8, column=0, sticky="ew", padx=16, pady=(8, 16))
        theme_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(theme_box, text="Тема оформления",
                     text_color=MUTED_COLOR).grid(row=0, column=0, sticky="w")
        self.seg_theme = ctk.CTkSegmentedButton(
            theme_box, values=list(THEMES), command=self._set_theme)
        self.seg_theme.set("Система")
        self.seg_theme.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # ===== правая панель: предпросмотр =====
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(14, 16), pady=14)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        self.seg_view = ctk.CTkSegmentedButton(
            top, values=["Новый файл", "Исходный файл"],
            command=self._set_view_mode)
        self.seg_view.set(self.view_mode)
        self.seg_view.grid(row=0, column=0, sticky="w")
        self.lbl_view_info = ctk.CTkLabel(top, text="", text_color=MUTED_COLOR)
        self.lbl_view_info.grid(row=0, column=1, sticky="e")

        self.preview_frame = ctk.CTkFrame(main, corner_radius=12)
        self.preview_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        self.preview_frame.grid_propagate(False)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.lbl_preview = ctk.CTkLabel(
            self.preview_frame,
            text="Выберите PDF-файл,\nчтобы увидеть предпросмотр",
            font=ctk.CTkFont(size=16), text_color=MUTED_COLOR, image=None,
        )
        self.lbl_preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_frame.bind("<Configure>", self._on_preview_resize)

        nav = ctk.CTkFrame(main, fg_color="transparent")
        nav.grid(row=2, column=0)
        self.btn_prev = ctk.CTkButton(
            nav, text="◀  Назад", width=110, command=lambda: self._nav(-1))
        self.btn_prev.grid(row=0, column=0, padx=8)
        self.lbl_page = ctk.CTkLabel(nav, text="—", width=190)
        self.lbl_page.grid(row=0, column=1, padx=8)
        self.btn_next = ctk.CTkButton(
            nav, text="Вперёд  ▶", width=110, command=lambda: self._nav(1))
        self.btn_next.grid(row=0, column=2, padx=8)

    def _card(self, parent, row: int, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=6)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        return card

    # ------------------------------------------------------------- файлы
    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите PDF-файл",
            filetypes=[("PDF-файлы", "*.pdf"), ("Все файлы", "*.*")],
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        try:
            doc = fitz.open(path)
            if doc.needs_pass and not doc.authenticate(""):
                doc.close()
                self._status("Файл защищён паролем — такие файлы не поддерживаются.", error=True)
                return
            if doc.page_count == 0:
                doc.close()
                self._status("В файле нет страниц.", error=True)
                return
        except Exception as exc:
            self._status(f"Не удалось открыть файл: {exc}", error=True)
            return

        if self.doc is not None:
            self.doc.close()
        self.doc = doc
        self.src_path = path
        self.total = doc.page_count
        self.out_dir = os.path.dirname(path)
        self._name_manual = False
        self.last_output = None
        self.btn_show.configure(state="disabled")

        self.lbl_file.configure(
            text=f"{os.path.basename(path)}\nСтраниц: {self.total}",
            text_color=("gray10", "gray90"),
        )
        self.lbl_dir.configure(text=self.out_dir)
        self.var_start.set("1")
        self.var_end.set(str(self.total))
        self.cur = 0
        self._status("")
        self._on_range_change()
        self._update_controls()
        self._schedule_render()

    def choose_dir(self) -> None:
        d = filedialog.askdirectory(
            title="Папка для нового файла", initialdir=self.out_dir or None)
        if d:
            self.out_dir = d
            self.lbl_dir.configure(text=d)

    # --------------------------------------------------------- диапазон
    def _parse_range(self):
        """Вернуть (start, end, ошибка). Нумерация страниц — с единицы."""
        if not self.doc:
            return None, None, "Сначала выберите файл."
        try:
            start = int(self.var_start.get().strip())
            end = int(self.var_end.get().strip())
        except ValueError:
            return None, None, "Введите номера страниц цифрами."
        if start < 1 or end < 1:
            return None, None, "Номера страниц начинаются с 1."
        if start > self.total or end > self.total:
            return None, None, f"В файле всего {self.total} стр."
        if start > end:
            return None, None, "Начальная страница больше конечной."
        return start, end, None

    def _on_range_change(self, *_args) -> None:
        if not hasattr(self, "lbl_range"):
            return
        start, end, err = self._parse_range()
        if err:
            self.lbl_range.configure(
                text=err if self.doc else "", text_color=ERROR_COLOR)
        else:
            n = end - start + 1
            self.lbl_range.configure(
                text=f"В новом файле будет страниц: {n}", text_color=MUTED_COLOR)
            if not self._name_manual and self.src_path:
                stem = os.path.splitext(os.path.basename(self.src_path))[0]
                self.var_name.set(f"{stem}_{start}-{end}.pdf")
        if self.view_mode == "Новый файл":
            self.cur = 0
        self._update_controls()
        self._schedule_render()

    # ---------------------------------------------------------- предпросмотр
    def _page_indices(self) -> list[int]:
        """Индексы (с 0) страниц, которые показываются в текущем режиме."""
        if not self.doc:
            return []
        if self.view_mode == "Исходный файл":
            return list(range(self.total))
        start, end, err = self._parse_range()
        if err:
            return []
        return list(range(start - 1, end))

    def _set_view_mode(self, mode: str) -> None:
        self.view_mode = mode
        self.cur = 0
        self._update_controls()
        self._schedule_render()

    def _nav(self, delta: int) -> None:
        pages = self._page_indices()
        if not pages:
            return
        self.cur = max(0, min(len(pages) - 1, self.cur + delta))
        self._update_controls()
        self._schedule_render(0)

    def _key_nav(self, delta: int) -> None:
        if isinstance(self.focus_get(), tk.Entry):
            return
        self._nav(delta)

    def _on_preview_resize(self, _event) -> None:
        self._schedule_render()

    def _schedule_render(self, delay: int = 120) -> None:
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self._render_job = self.after(delay, self._render)

    def _render(self) -> None:
        self._render_job = None
        pages = self._page_indices()
        if not self.doc or not pages:
            msg = ("Выберите PDF-файл,\nчтобы увидеть предпросмотр"
                   if not self.doc else "Укажите корректный диапазон страниц")
            self.lbl_preview.configure(image=self._blank, text=msg)
            return

        self.cur = max(0, min(len(pages) - 1, self.cur))
        idx = pages[self.cur]

        avail_w = max(self.preview_frame.winfo_width() - 40, 100)
        avail_h = max(self.preview_frame.winfo_height() - 40, 100)
        try:
            page = self.doc[idx]
            rect = page.rect
            fit = min(avail_w / rect.width, avail_h / rect.height)
            fit = max(fit, 0.05)
            quality = min(2.0, 3000 / max(rect.width * fit, rect.height * fit))
            pix = page.get_pixmap(
                matrix=fitz.Matrix(fit * quality, fit * quality), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img,
                size=(int(rect.width * fit), int(rect.height * fit)),
            )
        except Exception as exc:
            self.lbl_preview.configure(
                image=self._blank, text=f"Ошибка предпросмотра: {exc}")
            return

        self.lbl_preview.configure(image=ctk_img, text="")

        self.lbl_page.configure(
            text=f"Страница {self.cur + 1} из {len(pages)}")
        self.lbl_view_info.configure(text=f"Страница оригинала: {idx + 1}")

    def _update_controls(self) -> None:
        pages = self._page_indices()
        has_pages = bool(pages)
        self.btn_prev.configure(
            state="normal" if has_pages and self.cur > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if has_pages and self.cur < len(pages) - 1 else "disabled")
        if not has_pages:
            self.lbl_page.configure(text="—")
            self.lbl_view_info.configure(text="")
        else:
            self.lbl_page.configure(text=f"Страница {self.cur + 1} из {len(pages)}")
            self.lbl_view_info.configure(
                text=f"Страница оригинала: {pages[self.cur] + 1}")
        _s, _e, err = self._parse_range()
        self.btn_create.configure(state="normal" if not err else "disabled")

    # ------------------------------------------------------------- создание
    def create_pdf(self) -> None:
        start, end, err = self._parse_range()
        if err:
            self._status(err, error=True)
            return

        name = self.var_name.get().strip()
        if not name:
            self._status("Введите название нового файла.", error=True)
            return
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        if any(ch in name for ch in '<>:"/\\|?*'):
            self._status('Название содержит недопустимые символы: <>:"/\\|?*', error=True)
            return

        out_path = os.path.join(self.out_dir, name)
        if os.path.abspath(out_path) == os.path.abspath(self.src_path):
            self._status("Нельзя перезаписать исходный файл — выберите другое название.", error=True)
            return
        if os.path.exists(out_path) and not messagebox.askyesno(
            APP_TITLE, f"Файл «{name}» уже существует.\nПерезаписать?"
        ):
            return

        try:
            reader = PdfReader(self.src_path)
            if reader.is_encrypted:
                reader.decrypt("")
            writer = PdfWriter()
            for i in range(start - 1, end):
                writer.add_page(reader.pages[i])
            with open(out_path, "wb") as fh:
                writer.write(fh)
        except Exception as exc:
            self._status(f"Ошибка при создании файла: {exc}", error=True)
            return

        self.last_output = out_path
        self.btn_show.configure(state="normal")
        self._status(f"Готово! Создан файл «{name}» ({end - start + 1} стр.)", ok=True)

    def open_result(self) -> None:
        if self.last_output and os.path.exists(self.last_output):
            open_in_system(self.last_output)

    # --------------------------------------------------------------- прочее
    def _status(self, text: str, error: bool = False, ok: bool = False) -> None:
        color = ERROR_COLOR if error else OK_COLOR if ok else MUTED_COLOR
        self.lbl_status.configure(text=text, text_color=color)

    def _set_theme(self, label: str) -> None:
        ctk.set_appearance_mode(THEMES[label])

    def _on_close(self) -> None:
        if self.doc is not None:
            self.doc.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
