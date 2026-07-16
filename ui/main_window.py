"""
Ventana principal de la aplicación (segunda iteración de UX).

Cambios clave respecto de la primera versión:
    - Ya no existe un banner blanco de ancho completo en la parte
      superior: el sidebar y el panel central comienzan inmediatamente
      debajo de la barra de título de Windows.
    - El título / indicador de conexión / motor de IA ahora viven en
      un encabezado delgado que pertenece únicamente a la columna de
      contenido (mismo color de fondo que la página, sin separación
      visual), no en una franja que cruce toda la ventana.
    - "Configuración" ya no abre una ventana nueva: es una página más
      dentro del panel principal, exactamente igual que Inicio,
      Nuevo Chat e Historial.
    - El historial es real (SQLite) y permite restaurar cualquier
      conversación anterior sin perder nada.
"""
import threading

import customtkinter as ctk

from ai.copilot import GitHubCopilotProvider
from ai.gemini import GeminiProvider
from ai.openai import OpenAIProvider
from config.app_config import AppConfig
from models.message import Message, Sender
from services.conversation_service import ConversationService
from ui import theme
from ui.chat_panel import ChatPanel, HistoryPanel
from ui.settings_window import SettingsPage
from ui.sidebar import Sidebar
from ui.status_bar import StatusBar

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

CONNECTION_STATES = {
    "disconnected": "🔴 Sin conexión",
    "connecting": "🟡 Conectando...",
    "connected": "🟢 IA conectada",
}

AI_PROVIDERS = {
    "GitHub Copilot": GitHubCopilotProvider,
    "OpenAI": OpenAIProvider,
    "Gemini": GeminiProvider,
}


class ContentHeader(ctk.CTkFrame):
    """
    Encabezado delgado, propio de la columna de contenido (no de toda
    la ventana). Usa el mismo color de fondo que la página para que no
    se perciba como un banner separado.
    """

    def __init__(self, master, on_engine_change=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, height=44, **kwargs)
        self._on_engine_change = on_engine_change
        self.grid_propagate(False)
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            self,
            text="Asistente IA - La Vianda",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.grid(row=0, column=0, padx=(20, 8), pady=8, sticky="w")

        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.grid(row=0, column=1, sticky="ew")

        engine_label = ctk.CTkLabel(
            self,
            text="Motor IA:",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        engine_label.grid(row=0, column=2, padx=(0, 6), pady=8)

        self.engine_menu = ctk.CTkOptionMenu(
            self,
            values=["GitHub Copilot", "OpenAI", "Gemini", "Offline"],
            width=140,
            height=26,
            fg_color=theme.PRIMARY_BLUE_LIGHT,
            text_color=theme.PRIMARY_BLUE,
            button_color=theme.PRIMARY_BLUE,
            button_hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._handle_engine_change,
        )
        self.engine_menu.grid(row=0, column=3, padx=(0, 12), pady=8)

        self.status_label = ctk.CTkLabel(
            self,
            text=CONNECTION_STATES["disconnected"],
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.status_label.grid(row=0, column=4, padx=(0, 20), pady=8)

    def _handle_engine_change(self, value: str) -> None:
        if self._on_engine_change:
            self._on_engine_change(value)

    def set_connection_state(self, state: str) -> None:
        """state: 'disconnected' | 'connecting' | 'connected'"""
        self.status_label.configure(text=CONNECTION_STATES.get(state, CONNECTION_STATES["disconnected"]))

    def set_engine(self, engine_name: str) -> None:
        self.engine_menu.set(engine_name)


class MainWindow(ctk.CTk):
    """Ventana principal de Asistente IA - La Vianda."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Asistente IA - La Vianda")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self._config = AppConfig()
        ctk.set_appearance_mode("dark" if self._config.settings.theme == "dark" else "light")

        self._conversation_service = ConversationService()
        self._active_conversation_id: int | None = None
        self._current_view = "home"
        self._active_provider = None
        self._generating_job = None
        self._stop_requested = False

        self._build_layout()
        self._apply_initial_state()

    # ------------------------------------------------------------------ #
    # Construcción de la interfaz (sidebar y contenido comienzan en fila 0,
    # sin ninguna franja/espacio por encima)
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = Sidebar(self, on_navigate=self._handle_navigate)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.content_container = ctk.CTkFrame(self, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_rowconfigure(1, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        self.content_header = ContentHeader(self.content_container, on_engine_change=self._handle_engine_change)
        self.content_header.grid(row=0, column=0, sticky="ew")

        # Páginas apiladas en la misma celda (row=1); se muestra una a la vez.
        self.chat_panel = ChatPanel(
            self.content_container,
            on_send_message=self._handle_user_message,
            on_stop_generation=self._handle_stop_generation,
        )
        self.history_panel = HistoryPanel(
            self.content_container, on_select_conversation=self._handle_open_conversation
        )
        self.settings_page = SettingsPage(
            self.content_container,
            on_theme_change=self._apply_theme,
            on_ai_connection_change=self._handle_ai_connection_result,
            on_db_connection_change=self._handle_db_connection_result,
        )

        self.chat_panel.grid(row=1, column=0, sticky="nsew")

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _apply_initial_state(self) -> None:
        self.sidebar.select("home")
        self.content_header.set_engine(self._config.settings.ai_engine)
        self.content_header.set_connection_state("disconnected")
        self.status_bar.set_ai_status(False)
        self.status_bar.set_db_status(False)
        self.status_bar.set_user("Administrador")

    # ------------------------------------------------------------------ #
    # Navegación por páginas (todo dentro del mismo Frame principal,
    # nunca se abre una ventana nueva)
    # ------------------------------------------------------------------ #
    def _hide_all_pages(self) -> None:
        self.chat_panel.grid_forget()
        self.history_panel.grid_forget()
        self.settings_page.grid_forget()

    def _handle_navigate(self, key: str) -> None:
        # Si el usuario estaba en Configuración y navega a otra página,
        # persistimos los cambios antes de salir de esa vista.
        if self._current_view == "settings" and key != "settings":
            self.settings_page.save()

        self._current_view = key
        self._hide_all_pages()

        if key == "home":
            self.chat_panel.grid(row=1, column=0, sticky="nsew")
            self.chat_panel.show_welcome()
            self._active_conversation_id = None

        elif key == "new_chat":
            conversation = self._conversation_service.start_new_conversation()
            self._active_conversation_id = conversation.id
            self.chat_panel.grid(row=1, column=0, sticky="nsew")
            self.chat_panel.start_new_conversation()

        elif key == "history":
            self.history_panel.grid(row=1, column=0, sticky="nsew")
            grouped = self._conversation_service.list_grouped_conversations()
            self.history_panel.refresh(grouped)

        elif key == "settings":
            self.settings_page.grid(row=1, column=0, sticky="nsew")

    def _handle_open_conversation(self, conversation_id: int) -> None:
        """Restaura una conversación existente (NO crea una nueva)."""
        self._active_conversation_id = conversation_id
        messages = self._conversation_service.get_conversation_messages(conversation_id)

        self._current_view = "new_chat"  # se comporta como vista de chat activo
        self._hide_all_pages()
        self.chat_panel.grid(row=1, column=0, sticky="nsew")
        self.chat_panel.load_conversation(messages)
        self.sidebar.select("history")

    # ------------------------------------------------------------------ #
    # Tema
    # ------------------------------------------------------------------ #
    def _apply_theme(self, theme_mode: str) -> None:
        ctk.set_appearance_mode(theme_mode)

    # ------------------------------------------------------------------ #
    # Motor de IA (indicador dinámico de conexión)
    # ------------------------------------------------------------------ #
    def _handle_engine_change(self, engine_name: str) -> None:
        self.content_header.set_engine(engine_name)
        self._config.update(ai_engine=engine_name)

        if engine_name == "Offline":
            self.set_connection_state("disconnected")
            self.status_bar.set_ai_status(False)
            return

        provider_cls = AI_PROVIDERS.get(engine_name)
        self.set_connection_state("connecting")

        def finish_connection_attempt():
            connected = False
            if provider_cls is not None:
                self._active_provider = provider_cls()
                settings = self._config.settings
                connected, _message = self._active_provider.connect(
                    endpoint=settings.ai_endpoint, api_key=settings.ai_api_key
                )
            # Sin credenciales válidas o sin red, la conexión no se completa.
            self.set_connection_state("connected" if connected else "disconnected")
            self.status_bar.set_ai_status(connected, engine_name)

        self.after(700, finish_connection_attempt)

    def set_connection_state(self, state: str) -> None:
        """Permite cambiar el indicador de conexión dinámicamente desde el código."""
        self.content_header.set_connection_state(state)

    def _handle_ai_connection_result(self, engine_name: str, connected: bool, provider) -> None:
        """
        Se llama desde la tarjeta de IA en Configuración cuando el usuario
        presiona "Probar conexión". Antes este resultado se quedaba solo
        en esa tarjeta; ahora también actualiza el encabezado y la barra
        de estado, y deja el proveedor listo para usarse en el chat.
        """
        self._active_provider = provider  # None si no se pudo conectar
        self._config.update(ai_engine=engine_name)
        self.content_header.set_engine(engine_name)
        self.content_header.set_connection_state("connected" if connected else "disconnected")
        self.status_bar.set_ai_status(connected, engine_name)

    def _handle_db_connection_result(self, connected: bool, message: str) -> None:
        """Igual que arriba, pero para la tarjeta de Base de Datos."""
        self.status_bar.set_db_status(connected, "SQL Server")

    # ------------------------------------------------------------------ #
    # Envío de mensajes (con persistencia real en SQLite y respuesta real
    # del proveedor de IA cuando hay uno conectado)
    # ------------------------------------------------------------------ #
    def _handle_user_message(self, text: str) -> None:
        if self._active_conversation_id is None:
            # Red de seguridad: si por algún motivo no hay conversación activa
            # (por ejemplo, se escribió desde Inicio), se crea una al vuelo.
            conversation = self._conversation_service.start_new_conversation()
            self._active_conversation_id = conversation.id

        message = self._conversation_service.add_user_message(self._active_conversation_id, text)
        self.chat_panel.add_message(message)
        self.chat_panel.set_generating(True)
        self.chat_panel.show_typing_indicator()

        self._stop_requested = False

        if self._active_provider is not None and self._active_provider.is_connected():
            self._start_real_ai_response(text)
        else:
            # Sin proveedor conectado (Offline o conexión fallida): se explica
            # la situación en vez de fingir una respuesta.
            self._generating_job = self.after(900, lambda: self._finish_ai_response_placeholder(text))

    def _start_real_ai_response(self, text: str) -> None:
        """Llama al proveedor real en un hilo aparte para no congelar la interfaz."""
        provider = self._active_provider
        conversation_id = self._active_conversation_id

        def worker() -> None:
            try:
                reply_text = provider.send_message(text)
                error_text = None
            except Exception as exc:  # noqa: BLE001 - cualquier fallo de red/API se muestra al usuario
                reply_text = None
                error_text = str(exc)

            # Los widgets de Tk solo deben tocarse desde el hilo principal.
            self.after(0, lambda: self._finish_ai_response_real(conversation_id, reply_text, error_text))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_ai_response_real(self, conversation_id: int, reply_text: str | None, error_text: str | None) -> None:
        if self._stop_requested or conversation_id != self._active_conversation_id:
            # El usuario pidió detener, o ya cambió de conversación mientras
            # se esperaba la respuesta: no se muestra un mensaje fuera de lugar.
            return

        self.chat_panel.hide_typing_indicator()
        self.chat_panel.set_generating(False)

        if error_text:
            reply_text = f"⚠️ No se pudo obtener respuesta de {self._active_provider.name}: {error_text}"
            # Si el proveedor falló (token vencido, sin red, etc.), reflejarlo
            # también en el encabezado y la barra de estado.
            self.content_header.set_connection_state("disconnected")
            self.status_bar.set_ai_status(False, self._active_provider.name)

        message = self._conversation_service.add_assistant_message(conversation_id, reply_text)
        self.chat_panel.add_message(message)

    def _finish_ai_response_placeholder(self, original_text: str) -> None:
        """Respuesta simulada, solo quando no hay ningún proveedor de IA conectado."""
        self.chat_panel.hide_typing_indicator()
        self.chat_panel.set_generating(False)
        self._generating_job = None

        reply_text = (
            "Todavía no tengo un motor de IA conectado, así que no puedo "
            "responder de verdad. Conecta GitHub Copilot, OpenAI o Gemini "
            "desde Configuración para procesar tu consulta sobre: "
            f"\u00ab{original_text[:60]}\u00bb"
        )
        message = self._conversation_service.add_assistant_message(self._active_conversation_id, reply_text)
        self.chat_panel.add_message(message)

    def _handle_stop_generation(self) -> None:
        self._stop_requested = True
        if self._generating_job is not None:
            self.after_cancel(self._generating_job)
            self._generating_job = None
        self.chat_panel.hide_typing_indicator()
        self.chat_panel.set_generating(False)

        stop_message = self._conversation_service.add_assistant_message(
            self._active_conversation_id, "(Generación detenida por el usuario)"
        )
        self.chat_panel.add_message(stop_message)
