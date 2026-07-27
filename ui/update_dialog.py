import customtkinter as ctk
from PIL import Image

from models.update_info import UpdateInfo
from services.update_manager import UpdateManager
from ui import theme
from ui.assets_path import get_asset_path

_LOGO_PATH = get_asset_path("logo.png")


def _format_speed(bytes_per_second: float) -> str:
    if bytes_per_second >= 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
    return f"{bytes_per_second / 1024:.0f} KB/s"


def _format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / 1024:.0f} KB"


class UpdateDialog(ctk.CTkToplevel):

    def __init__(
        self,
        master,
        update_manager: UpdateManager,
        update_info: UpdateInfo,
        current_version: str,
        on_remind_later=None,
        on_ready_to_install=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title("Actualización disponible")
        self.geometry("400x560")
        self.minsize(400, 500)
        self.configure(fg_color=theme.SURFACE_WHITE)

        self._update_manager = update_manager
        self._update_info = update_info
        self._current_version = current_version
        self._on_remind_later = on_remind_later
        self._on_ready_to_install = on_ready_to_install
        self._cancel_requested = False

        header = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG, corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.place(relx=0.5, rely=0.5, anchor="center")

        try:
            logo_image = ctk.CTkImage(Image.open(_LOGO_PATH), size=(22, 22))
            logo_label = ctk.CTkLabel(header_content, image=logo_image, text="")
            logo_label.pack(side="left", padx=(0, 8))
        except Exception:
            pass

        ctk.CTkLabel(
            header_content,
            text="Nueva versión disponible",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color="#FFFFFF",
        ).pack(side="left")

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=24, pady=20)

        self._build_info_view()

        self.transient(master)
        self.after(10, self.lift)
        self.grab_set()

    def _clear_container(self) -> None:
        for widget in self._container.winfo_children():
            widget.destroy()

    def _build_info_view(self) -> None:
        self._clear_container()

        button_row = ctk.CTkFrame(self._container, fg_color="transparent")
        button_row.pack(side="bottom", fill="x", pady=(12, 0))

        if not self._update_info.mandatory:
            later_button = ctk.CTkButton(
                button_row,
                text="Más tarde",
                height=38,
                fg_color="transparent",
                border_width=1,
                border_color=theme.BORDER_LIGHT,
                text_color=theme.TEXT_DARK,
                hover_color=theme.BACKGROUND_LIGHT,
                command=self._handle_remind_later,
            )
            later_button.pack(side="left", fill="x", expand=True, padx=(0, 8))

        update_button = ctk.CTkButton(
            button_row,
            text="Actualizar ahora",
            height=38,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            command=self._start_download,
        )
        update_button.pack(side="left", fill="x", expand=True)

        compare_row = ctk.CTkFrame(self._container, fg_color="transparent")
        compare_row.pack(pady=(4, 2))

        installed_col = ctk.CTkFrame(compare_row, fg_color="transparent")
        installed_col.pack(side="left", padx=14)
        ctk.CTkLabel(
            installed_col, text="Instalada", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=10),
            text_color=theme.TEXT_MUTED,
        ).pack()
        ctk.CTkLabel(
            installed_col, text=self._current_version,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17, weight="bold"), text_color=theme.TEXT_DARK,
        ).pack()

        ctk.CTkLabel(
            compare_row, text="→", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=theme.PRIMARY_RED,
        ).pack(side="left", padx=4)

        new_col = ctk.CTkFrame(compare_row, fg_color="transparent")
        new_col.pack(side="left", padx=14)
        ctk.CTkLabel(
            new_col, text="Nueva", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=10),
            text_color=theme.STATUS_RED,
        ).pack()
        ctk.CTkLabel(
            new_col, text=self._update_info.version,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17, weight="bold"), text_color=theme.PRIMARY_RED,
        ).pack()

        ctk.CTkLabel(
            self._container,
            text=f"Publicada el {self._update_info.published}" if self._update_info.published else "",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(2, 16))

        if self._update_info.mandatory:
            mandatory_label = ctk.CTkLabel(
                self._container,
                text="⚠️ Esta actualización es obligatoria para seguir usando el asistente.",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
                text_color=theme.STATUS_RED,
                wraplength=340,
                justify="left",
            )
            mandatory_label.pack(pady=(0, 12))

        notes_title = ctk.CTkLabel(
            self._container,
            text="Novedades de esta versión",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        notes_title.pack(anchor="w", pady=(0, 6))

        notes_frame = ctk.CTkScrollableFrame(self._container, fg_color=theme.BACKGROUND_LIGHT, corner_radius=theme.CORNER_RADIUS)
        notes_frame.pack(fill="both", expand=True, pady=(0, 16))

        if self._update_info.release_notes:
            for note in self._update_info.release_notes:
                note_label = ctk.CTkLabel(
                    notes_frame,
                    text=f"•  {note}",
                    font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                    text_color="#5F5E5A",
                    wraplength=320,
                    justify="left",
                    anchor="w",
                )
                note_label.pack(anchor="w", padx=12, pady=3, fill="x")
        else:
            empty_label = ctk.CTkLabel(
                notes_frame,
                text="Sin notas de la versión.",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_MUTED,
            )
            empty_label.pack(padx=12, pady=8)

    def _handle_remind_later(self) -> None:
        self.destroy()
        if self._on_remind_later:
            self._on_remind_later()

    def _start_download(self) -> None:
        self._cancel_requested = False
        self._build_progress_view()
        self._update_manager.download_update(
            self._update_info,
            on_progress=self._handle_progress,
            on_complete=self._handle_download_complete,
            should_cancel=lambda: self._cancel_requested,
        )

    def _build_progress_view(self) -> None:
        self._clear_container()

        title = ctk.CTkLabel(
            self._container,
            text=f"Descargando la versión {self._update_info.version}...",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=16, weight="bold"),
            text_color=theme.TEXT_DARK,
            wraplength=340,
        )
        title.pack(anchor="w", pady=(20, 16))

        self._progress_bar = ctk.CTkProgressBar(self._container, progress_color=theme.PRIMARY_RED)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(0, 8))

        status_row = ctk.CTkFrame(self._container, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 24))

        self._percent_label = ctk.CTkLabel(
            status_row, text="0%", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        self._percent_label.pack(side="left")

        self._speed_label = ctk.CTkLabel(
            status_row, text="", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        self._speed_label.pack(side="right")

        self._status_label = ctk.CTkLabel(
            self._container, text="", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.STATUS_RED, wraplength=340, justify="left",
        )
        self._status_label.pack(anchor="w", pady=(0, 12))

        self._cancel_button = ctk.CTkButton(
            self._container, text="Cancelar", fg_color="transparent", border_width=1,
            border_color=theme.BORDER_LIGHT, text_color=theme.TEXT_DARK, hover_color=theme.BACKGROUND_LIGHT,
            command=self._handle_cancel,
        )
        self._cancel_button.pack(fill="x")

    def _handle_progress(self, downloaded: int, total: int, speed: float, percent: float) -> None:
        self.after(0, lambda: self._update_progress_ui(downloaded, total, speed, percent))

    def _update_progress_ui(self, downloaded: int, total: int, speed: float, percent: float) -> None:
        try:
            self._progress_bar.set(min(percent / 100, 1.0))
            size_text = f"{_format_size(downloaded)} / {_format_size(total)}" if total else _format_size(downloaded)
            self._percent_label.configure(text=f"{percent:.0f}%  ·  {size_text}")
            self._speed_label.configure(text=_format_speed(speed))
        except Exception:
            pass

    def _handle_cancel(self) -> None:
        self._cancel_requested = True
        self._cancel_button.configure(state="disabled", text="Cancelando...")

    def _handle_download_complete(self, success: bool, path, error) -> None:
        self.after(0, lambda: self._on_download_complete_ui(success, path, error))

    def _on_download_complete_ui(self, success: bool, path, error) -> None:
        if success:
            self.destroy()
            if self._on_ready_to_install:
                self._on_ready_to_install(path)
            return

        try:
            self._status_label.configure(text=f"⚠️ {error}")
            self._cancel_button.configure(state="normal", text="Volver", command=self._build_info_view)
        except Exception:
            pass
