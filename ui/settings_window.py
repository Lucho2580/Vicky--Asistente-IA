"""
Página de Configuración (integrada, sin ventanas nuevas).

A diferencia de la primera iteración, ya no es un `CTkToplevel`: es un
`CTkFrame` más que se muestra dentro del panel principal, exactamente
igual que Inicio, Nuevo Chat o Historial. Se organiza en tarjetas
(Cards): IA/Copilot, Base de Datos, Apariencia y Sistema.
"""
import os
import subprocess
import sys

import customtkinter as ctk

from ai.copilot import GitHubCopilotProvider
from ai.gemini import GeminiProvider
from ai.openai import OpenAIProvider
from config.app_config import AppConfig
from core.paths import CONVERSATIONS_DB_PATH, LOGS_DIR
from database.sqlserver import SQLServerCredentials, SQLServerDatabase
from ui import theme

APP_VERSION = "0.2.0"

AI_ENGINES = ["Offline", "GitHub Copilot", "OpenAI", "Gemini"]
AI_PROVIDER_MAP = {
    "GitHub Copilot": GitHubCopilotProvider,
    "OpenAI": OpenAIProvider,
    "Gemini": GeminiProvider,
}


class Card(ctk.CTkFrame):
    """Tarjeta reutilizable con título, descripción y contenido propio."""

    def __init__(self, master, title: str, description: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            **kwargs,
        )
        self._build_header(title, description)

    def _build_header(self, title: str, description: str) -> None:
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(anchor="w", padx=20, pady=(16, 2))

        if description:
            desc_label = ctk.CTkLabel(
                self,
                text=description,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_MUTED,
            )
            desc_label.pack(anchor="w", padx=20, pady=(0, 10))

    def add_field(self, label_text: str, widget_cls, **widget_kwargs):
        """Agrega una fila de campo (etiqueta + widget) al cuerpo de la tarjeta."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)

        label = ctk.CTkLabel(
            row,
            text=label_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            width=140,
            anchor="w",
        )
        label.pack(side="left")

        widget = widget_cls(row, **widget_kwargs)
        widget.pack(side="left", fill="x", expand=True)
        return widget

    def add_footer_spacer(self) -> None:
        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()


class SettingsPage(ctk.CTkScrollableFrame):
    """Página completa de configuración, dividida en tarjetas."""

    def __init__(self, master, on_theme_change=None, on_ai_connection_change=None, on_db_connection_change=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._config = AppConfig()
        self._on_theme_change = on_theme_change
        self._on_ai_connection_change = on_ai_connection_change
        self._on_db_connection_change = on_db_connection_change
        self._build_ai_card()
        self._build_database_card()
        self._build_appearance_card()
        self._build_system_card()

    # ------------------------------------------------------------------ #
    # Tarjeta: COPILOT / IA
    # ------------------------------------------------------------------ #
    def _build_ai_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "COPILOT / IA", "Configura el motor de inteligencia artificial que responderá tus consultas.")
        card.pack(fill="x", padx=24, pady=(20, 12))

        self._ai_engine_var = ctk.StringVar(
            value=settings.ai_engine if settings.ai_engine in AI_ENGINES else "Offline"
        )
        radio_row = ctk.CTkFrame(card, fg_color="transparent")
        radio_row.pack(fill="x", padx=20, pady=(0, 6))
        for engine in AI_ENGINES:
            ctk.CTkRadioButton(
                radio_row,
                text=engine,
                value=engine,
                variable=self._ai_engine_var,
                fg_color=theme.PRIMARY_BLUE,
            ).pack(side="left", padx=(0, 16))

        self.ai_endpoint_entry = card.add_field("Endpoint", ctk.CTkEntry, placeholder_text="https://...")
        self.ai_endpoint_entry.insert(0, settings.ai_endpoint)

        self.ai_api_key_entry = card.add_field("API Key", ctk.CTkEntry, show="•")
        self.ai_api_key_entry.insert(0, settings.ai_api_key)

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(8, 4))

        test_button = ctk.CTkButton(
            button_row,
            text="Probar conexión",
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_BLUE,
            hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._test_ai_connection,
        )
        test_button.pack(side="left")

        self.ai_status_label = ctk.CTkLabel(
            button_row,
            text="🔴 Desconectado",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.ai_status_label.pack(side="left", padx=12)

        self.ai_detail_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
            wraplength=520,
            justify="left",
        )
        self.ai_detail_label.pack(anchor="w", padx=20, pady=(0, 4))
        card.add_footer_spacer()

    def _test_ai_connection(self) -> None:
        engine = self._ai_engine_var.get()
        provider_cls = AI_PROVIDER_MAP.get(engine)

        if engine == "Offline" or provider_cls is None:
            self.ai_status_label.configure(text="🔴 Desconectado")
            self.ai_detail_label.configure(
                text="Selecciona un motor de IA distinto de Offline para probar la conexión."
            )
            if self._on_ai_connection_change:
                self._on_ai_connection_change(engine, False, None)
            return

        provider = provider_cls()
        connected, message = provider.connect(
            endpoint=self.ai_endpoint_entry.get(), api_key=self.ai_api_key_entry.get()
        )
        self.ai_status_label.configure(text="🟢 Conectado" if connected else "🔴 Desconectado")
        self.ai_detail_label.configure(text=message)

        # Avisa a la ventana principal para que la barra de estado y el
        # encabezado reflejen este resultado (antes quedaban desincronizados).
        if self._on_ai_connection_change:
            self._on_ai_connection_change(engine, connected, provider if connected else None)

    # ------------------------------------------------------------------ #
    # Tarjeta: BASE DE DATOS
    # ------------------------------------------------------------------ #
    def _build_database_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "BASE DE DATOS", "Datos de conexión al servidor SQL Server corporativo de La Vianda.")
        card.pack(fill="x", padx=24, pady=12)

        self.db_server_entry = card.add_field("Servidor", ctk.CTkEntry)
        self.db_server_entry.insert(0, settings.db_server)

        self.db_name_entry = card.add_field("Base", ctk.CTkEntry)
        self.db_name_entry.insert(0, settings.db_name)

        self.db_user_entry = card.add_field("Usuario", ctk.CTkEntry)
        self.db_user_entry.insert(0, settings.db_user)

        self.db_password_entry = card.add_field("Contraseña", ctk.CTkEntry, show="•")
        self.db_password_entry.insert(0, settings.db_password)

        self.db_connection_string_entry = card.add_field("Cadena de conexión", ctk.CTkEntry)
        self.db_connection_string_entry.insert(0, settings.connection_string)

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(8, 4))

        test_button = ctk.CTkButton(
            button_row,
            text="Probar conexión",
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_BLUE,
            hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._test_db_connection,
        )
        test_button.pack(side="left")

        self.db_status_label = ctk.CTkLabel(
            button_row,
            text="🔴 Sin conexión",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.db_status_label.pack(side="left", padx=12)

        self.db_detail_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
            wraplength=520,
            justify="left",
        )
        self.db_detail_label.pack(anchor="w", padx=20, pady=(0, 4))
        card.add_footer_spacer()

    def _test_db_connection(self) -> None:
        credentials = SQLServerCredentials(
            server=self.db_server_entry.get(),
            database=self.db_name_entry.get(),
            user=self.db_user_entry.get(),
            password=self.db_password_entry.get(),
            connection_string=self.db_connection_string_entry.get(),
        )
        db = SQLServerDatabase(credentials)
        connected, message = db.connect()
        self.db_status_label.configure(
            text="🟢 SQL Server conectado" if connected else "🔴 Sin conexión"
        )
        self.db_detail_label.configure(text=message)

        if self._on_db_connection_change:
            self._on_db_connection_change(connected, message)

    # ------------------------------------------------------------------ #
    # Tarjeta: APARIENCIA
    # ------------------------------------------------------------------ #
    def _build_appearance_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "APARIENCIA", "Personaliza cómo se ve la aplicación.")
        card.pack(fill="x", padx=24, pady=12)

        theme_map = {"light": "Claro", "dark": "Oscuro", "auto": "Automático"}
        self._theme_var = ctk.StringVar(value=theme_map.get(settings.theme, "Claro"))
        radio_row = ctk.CTkFrame(card, fg_color="transparent")
        radio_row.pack(fill="x", padx=20, pady=(0, 6))
        for label in ["Claro", "Oscuro", "Automático"]:
            ctk.CTkRadioButton(
                radio_row,
                text=label,
                value=label,
                variable=self._theme_var,
                fg_color=theme.PRIMARY_BLUE,
                command=self._apply_theme_now,
            ).pack(side="left", padx=(0, 16))

        self.scale_menu = card.add_field(
            "Escala de interfaz", ctk.CTkOptionMenu, values=["80%", "90%", "100%", "110%", "120%"]
        )
        self.scale_menu.set(settings.ui_scale)

        self.language_menu = card.add_field(
            "Idioma", ctk.CTkOptionMenu, values=["Español", "English"]
        )
        self.language_menu.set("Español" if settings.language == "es" else "English")
        card.add_footer_spacer()

    def _apply_theme_now(self) -> None:
        label_to_mode = {"Claro": "light", "Oscuro": "dark", "Automático": "system"}
        mode = label_to_mode.get(self._theme_var.get(), "light")
        ctk.set_appearance_mode(mode)
        if self._on_theme_change:
            self._on_theme_change(mode)

    # ------------------------------------------------------------------ #
    # Tarjeta: SISTEMA
    # ------------------------------------------------------------------ #
    def _build_system_card(self) -> None:
        card = Card(self, "SISTEMA", "Información de la instalación y accesos rápidos.")
        card.pack(fill="x", padx=24, pady=(12, 24))

        version_entry = card.add_field("Versión", ctk.CTkEntry)
        version_entry.insert(0, APP_VERSION)
        version_entry.configure(state="disabled")

        logs_entry = card.add_field("Ruta de logs", ctk.CTkEntry)
        logs_entry.insert(0, str(LOGS_DIR))
        logs_entry.configure(state="disabled")

        conversations_entry = card.add_field("Carpeta de conversaciones", ctk.CTkEntry)
        conversations_entry.insert(0, str(CONVERSATIONS_DB_PATH.parent))
        conversations_entry.configure(state="disabled")

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(8, 4))

        open_button = ctk.CTkButton(
            button_row,
            text="Abrir carpeta",
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_BLUE,
            hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._open_conversations_folder,
        )
        open_button.pack(side="left")
        card.add_footer_spacer()

    def _open_conversations_folder(self) -> None:
        folder = CONVERSATIONS_DB_PATH.parent
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception:
            # Si no hay gestor de archivos disponible (ej. entorno de pruebas
            # sin escritorio), se ignora silenciosamente: no es un error crítico.
            pass

    # ------------------------------------------------------------------ #
    # Guardado (se llama al salir de la página, ver MainWindow)
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        label_to_theme = {"Claro": "light", "Oscuro": "dark", "Automático": "auto"}
        self._config.update(
            ai_engine=self._ai_engine_var.get(),
            ai_endpoint=self.ai_endpoint_entry.get(),
            ai_api_key=self.ai_api_key_entry.get(),
            db_server=self.db_server_entry.get(),
            db_name=self.db_name_entry.get(),
            db_user=self.db_user_entry.get(),
            db_password=self.db_password_entry.get(),
            connection_string=self.db_connection_string_entry.get(),
            theme=label_to_theme.get(self._theme_var.get(), "light"),
            ui_scale=self.scale_menu.get(),
            language="es" if self.language_menu.get() == "Español" else "en",
        )
