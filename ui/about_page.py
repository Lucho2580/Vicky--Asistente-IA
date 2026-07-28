import platform

import customtkinter as ctk
from PIL import Image

from config.app_config import AppConfig
from core.audio_recorder import has_input_device
from core.version import APP_BUILD, APP_VERSION, BUILD_DATE
from ui import theme
from ui.assets_path import get_asset_path

_LOGO_PATH = get_asset_path("logo.png")


class StatusTile(ctk.CTkFrame):

    def __init__(self, master, label_text: str, **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            **kwargs,
        )
        ctk.CTkLabel(
            self,
            text=label_text.upper(),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(10, 2))

        self.value_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
        )
        self.value_label.pack(anchor="w", padx=14, pady=(0, 10))

    def set_value(self, text: str, color: str) -> None:
        self.value_label.configure(text=text, text_color=color)


class AboutPage(ctk.CTkScrollableFrame):

    def __init__(self, master, display_name: str | None = None, on_check_updates_now=None, get_ai_status=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._display_name = display_name
        self._on_check_updates_now = on_check_updates_now
        self._get_ai_status = get_ai_status
        self._config = AppConfig()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 14))

        try:
            logo_image = ctk.CTkImage(Image.open(_LOGO_PATH), size=(48, 48))
            logo_label = ctk.CTkLabel(header, image=logo_image, text="")
        except Exception:
            logo_label = ctk.CTkLabel(header, text="🙋", font=ctk.CTkFont(size=32))
        logo_label.pack(side="left", padx=(0, 12))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left")

        ctk.CTkLabel(
            title_col, text="Vicky",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17, weight="bold"),
            text_color=theme.TEXT_DARK,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_col, text=f"Versión {APP_VERSION}  ·  Build {APP_BUILD}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24, pady=(0, 10))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        self.ai_tile = StatusTile(grid, "Motor de IA")
        self.ai_tile.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.keyring_tile = StatusTile(grid, "Llavero seguro")
        self.keyring_tile.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)

        self.mic_tile = StatusTile(grid, "Micrófono")
        self.mic_tile.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.update_tile = StatusTile(grid, "Última actualización")
        self.update_tile.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

        actions_card = ctk.CTkFrame(
            self, fg_color=theme.SURFACE_WHITE, corner_radius=theme.CORNER_RADIUS,
            border_width=1, border_color=theme.BORDER_LIGHT,
        )
        actions_card.pack(fill="x", padx=24, pady=(0, 10))

        session_row = ctk.CTkFrame(actions_card, fg_color="transparent")
        session_row.pack(fill="x", padx=16, pady=(14, 8))

        self.session_label = ctk.CTkLabel(
            session_row, text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED, anchor="w", justify="left",
        )
        self.session_label.pack(side="left", fill="x", expand=True)

        button_row = ctk.CTkFrame(actions_card, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            button_row, text="Buscar actualizaciones", corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED, hover_color=theme.PRIMARY_RED_HOVER,
            command=self._handle_check_updates, width=150,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            button_row, text="Ver notas", corner_radius=theme.CORNER_RADIUS,
            fg_color="transparent", border_width=1, border_color=theme.BORDER_LIGHT,
            text_color=theme.TEXT_DARK, hover_color=theme.BACKGROUND_LIGHT,
            command=self._show_release_notes, width=90,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            button_row, text="📋 Copiar diagnóstico", corner_radius=theme.CORNER_RADIUS,
            fg_color="transparent", border_width=1, border_color=theme.BORDER_LIGHT,
            text_color=theme.TEXT_DARK, hover_color=theme.BACKGROUND_LIGHT,
            command=self._copy_diagnostics,
        ).pack(side="left")

        self._release_notes_label = ctk.CTkLabel(
            actions_card, text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK, wraplength=480, justify="left",
        )
        self._release_notes_label.pack(anchor="w", padx=16, pady=(0, 14))

        self._diagnostics_copied_label = ctk.CTkLabel(
            actions_card, text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.STATUS_GREEN,
        )
        self._diagnostics_copied_label.pack(anchor="w", padx=16, pady=(0, 10))

        footer_label = ctk.CTkLabel(
            self, text="Desarrollado para La Vianda.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        footer_label.pack(pady=(4, 20))

    def refresh(self) -> None:
        connected, engine_name = self._get_current_ai_status()
        if connected:
            self.ai_tile.set_value(f"🟢 {engine_name}", theme.STATUS_GREEN)
        else:
            self.ai_tile.set_value(f"🔴 {engine_name}" if engine_name else "🔴 Sin conexión", theme.STATUS_RED)

        if self._config.secure_storage_available:
            self.keyring_tile.set_value("🟢 Disponible", theme.STATUS_GREEN)
        else:
            self.keyring_tile.set_value("🟡 Modo de respaldo", theme.STATUS_YELLOW)

        if has_input_device():
            self.mic_tile.set_value("🟢 Detectado", theme.STATUS_GREEN)
        else:
            self.mic_tile.set_value("🟡 No detectado", theme.STATUS_YELLOW)

        last_check = self._config.settings.last_update_check
        last_check_text = last_check[:16].replace("T", " ") if last_check else "Nunca"
        self.update_tile.set_value(last_check_text, theme.TEXT_DARK)

        self.session_label.configure(
            text=f"{self._display_name or 'Invitado'}  ·  {engine_name}"
        )

        self._diagnostics_copied_label.configure(text="")

    def _get_current_ai_status(self) -> tuple:
        if self._get_ai_status:
            return self._get_ai_status()
        return False, self._config.settings.ai_engine or "Sin configurar"

    def _handle_check_updates(self) -> None:
        if self._on_check_updates_now:
            self._on_check_updates_now()

    def _show_release_notes(self) -> None:
        self._release_notes_label.configure(
            text=(
                f"Estás usando la versión {APP_VERSION} (build {APP_BUILD}). "
                "Las notas de una nueva versión se muestran automáticamente "
                "en el diálogo de actualización cuando hay una disponible."
            )
        )

    def _copy_diagnostics(self) -> None:
        connected, engine_name = self._get_current_ai_status()
        lines = [
            "Vicky — información de diagnóstico",
            f"Versión: {APP_VERSION} (build {APP_BUILD}, {BUILD_DATE})",
            f"Usuario: {self._display_name or 'Invitado'}",
            f"Motor de IA: {engine_name} ({'conectado' if connected else 'sin conexión'})",
            f"Llavero seguro: {'disponible' if self._config.secure_storage_available else 'modo de respaldo (texto plano)'}",
            f"Micrófono: {'detectado' if has_input_device() else 'no detectado'}",
            f"Sistema operativo: {platform.system()} {platform.release()}",
        ]
        text = "\n".join(lines)

        self.clipboard_clear()
        self.clipboard_append(text)
        self._diagnostics_copied_label.configure(text="✓ Copiado al portapapeles")
