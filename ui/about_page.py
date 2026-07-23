"""
Página "Acerca de": versión, build, fecha de compilación, última
actualización, sesión actual y ubicación de los datos. Se muestra
dentro del panel principal, no en una ventana aparte.
"""
import customtkinter as ctk

from config.app_config import AppConfig
from core.paths import CONVERSATIONS_DB_PATH, KNOWLEDGE_DB_PATH, LOGS_DIR, TRAINING_DIR
from core.version import APP_BUILD, APP_VERSION, BUILD_DATE
from ui import theme
from ui.settings_window import Card


class AboutPage(ctk.CTkScrollableFrame):
    """Información de versión, sesión actual y ubicación de los datos."""

    def __init__(self, master, display_name: str | None = None, on_check_updates_now=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._display_name = display_name
        self._on_check_updates_now = on_check_updates_now
        self._config = AppConfig()
        self._build_ui()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(32, 8))

        logo_label = ctk.CTkLabel(header, text="🤖", font=ctk.CTkFont(size=48))
        logo_label.pack()

        title_label = ctk.CTkLabel(
            header,
            text="Vicky Consulting",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=20, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(pady=(8, 2))

        version_label = ctk.CTkLabel(
            header,
            text=f"Versión {APP_VERSION}  ·  Build {APP_BUILD}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        version_label.pack()

        # --- Tarjeta de versión (version/build/fecha de compilación/última actualización) ---
        version_card = Card(self, "Versión")
        version_card.pack(fill="x", padx=24, pady=12)
        self._add_row(version_card, "Versión", APP_VERSION)
        self._add_row(version_card, "Build", str(APP_BUILD))
        self._add_row(version_card, "Fecha de compilación", BUILD_DATE)

        last_check = self._config.settings.last_update_check
        last_check_text = last_check[:16].replace("T", " ") if last_check else "Nunca"
        self._add_row(version_card, "Última actualización", last_check_text)

        button_row = ctk.CTkFrame(version_card, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(8, 4))

        check_updates_button = ctk.CTkButton(
            button_row, text="Buscar actualizaciones", corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED, hover_color=theme.PRIMARY_RED_HOVER,
            command=self._handle_check_updates,
        )
        check_updates_button.pack(side="left", padx=(0, 8))

        release_notes_button = ctk.CTkButton(
            button_row, text="Ver notas de la versión", corner_radius=theme.CORNER_RADIUS,
            fg_color="transparent", border_width=1, border_color=theme.BORDER_LIGHT,
            text_color=theme.TEXT_DARK, hover_color=theme.BACKGROUND_LIGHT,
            command=self._show_release_notes,
        )
        release_notes_button.pack(side="left")

        self._release_notes_label = ctk.CTkLabel(
            version_card, text="", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK, wraplength=480, justify="left",
        )
        self._release_notes_label.pack(anchor="w", padx=20, pady=(0, 8))
        version_card.add_footer_spacer()

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

    def _handle_check_updates(self) -> None:
        if self._on_check_updates_now:
            self._on_check_updates_now()

    def _show_release_notes(self) -> None:
        """
        Notas de la versión actual. Las notas de una versión NUEVA
        disponible se muestran automáticamente en el diálogo de
        actualización (ver ui/update_dialog.py); acá solo se informa
        la versión instalada, porque todavía no hay un historial de
        versiones pasadas guardado.
        """
        self._release_notes_label.configure(
            text=(
                f"Estás usando la versión {APP_VERSION} (build {APP_BUILD}). "
                "Las notas de una nueva versión se muestran automáticamente "
                "en el diálogo de actualización cuando hay una disponible."
            )
        )

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
