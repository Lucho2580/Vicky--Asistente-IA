"""
Página "Acerca de": versión de la app, sesión actual y ubicación de
los datos. Se muestra dentro del panel principal, no en una ventana
aparte.
"""
import customtkinter as ctk

from core.paths import CONVERSATIONS_DB_PATH, KNOWLEDGE_DB_PATH, LOGS_DIR, TRAINING_DIR
from ui import theme
from ui.settings_window import APP_VERSION, Card


class AboutPage(ctk.CTkScrollableFrame):
    """Información de versión, sesión actual y ubicación de los datos."""

    def __init__(self, master, display_name: str | None = None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._display_name = display_name
        self._build_ui()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(32, 8))

        logo_label = ctk.CTkLabel(header, text="🤖", font=ctk.CTkFont(size=48))
        logo_label.pack()

        title_label = ctk.CTkLabel(
            header,
            text="Asistente IA - La Vianda",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=20, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(pady=(8, 2))

        version_label = ctk.CTkLabel(
            header,
            text=f"Versión {APP_VERSION}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        version_label.pack()

        session_card = Card(self, "Sesión actual")
        session_card.pack(fill="x", padx=24, pady=12)
        self._add_row(session_card, "Usuario", self._display_name or "Sin identificar (login con Microsoft no usado)")
        self._add_row(session_card, "Motor de IA", "GitHub Copilot")
        session_card.add_footer_spacer()

        paths_card = Card(
            self,
            "Ubicación de los datos",
            "Toda la información se guarda localmente en esta computadora, no en la nube.",
        )
        paths_card.pack(fill="x", padx=24, pady=12)
        self._add_row(paths_card, "Conversaciones", str(CONVERSATIONS_DB_PATH))
        self._add_row(paths_card, "Base de conocimiento", str(KNOWLEDGE_DB_PATH))
        self._add_row(paths_card, "Carpeta Training", str(TRAINING_DIR))
        self._add_row(paths_card, "Logs", str(LOGS_DIR))
        paths_card.add_footer_spacer()

        footer_label = ctk.CTkLabel(
            self,
            text="Desarrollado para La Vianda.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        footer_label.pack(pady=(4, 20))

    def _add_row(self, card: Card, label_text: str, value_text: str) -> None:
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)

        label = ctk.CTkLabel(
            row,
            text=label_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            width=170,
            anchor="w",
        )
        label.pack(side="left")

        value_label = ctk.CTkLabel(
            row,
            text=value_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
            anchor="w",
            wraplength=380,
            justify="left",
        )
        value_label.pack(side="left", fill="x", expand=True)
