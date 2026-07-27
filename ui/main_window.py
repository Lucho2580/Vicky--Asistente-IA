import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ai.copilot import GitHubCopilotProvider
from config.app_config import AppConfig
from core.app_logger import get_logger
from core.greeting import build_greeting
from core.version import APP_BUILD, APP_VERSION, BUILD_DATE
from database.knowledge_store import KnowledgeStore
from models.message import Message, Sender
from services.connection_log_service import ConnectionLogService
from services.conversation_service import ConversationService
from services.knowledge_base import (
    SUPPORTED_TEXT_EXTENSIONS,
    KnowledgeBase,
    UnsupportedFileTypeError,
    friendly_name,
)
from services.qa_log_service import QALogService
from services.update_manager import UpdateManager
from ui import theme
from ui.about_page import AboutPage
from ui.chat_panel import ChatPanel, HistoryPanel
from ui.help_page import HelpPage
from ui.settings_window import SettingsPage
from ui.sidebar import Sidebar
from ui.status_bar import StatusBar
from ui.update_dialog import UpdateDialog

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

CONNECTION_STATES = {
    "disconnected": "🔴 Sin conexión",
    "connecting": "🟡 Conectando...",
    "connected": "🟢 IA conectada",
}

AI_ENGINE_NAME = "GitHub Copilot"
AI_PROVIDERS = {
    AI_ENGINE_NAME: GitHubCopilotProvider,
}


class ContentHeader(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, height=44, **kwargs)
        self.grid_propagate(False)
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            self,
            text="Vicky Consulting",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.grid(row=0, column=0, padx=(20, 8), pady=8, sticky="w")

        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.grid(row=0, column=1, sticky="ew")

        engine_label = ctk.CTkLabel(
            self,
            text=f"Motor IA: {AI_ENGINE_NAME}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        engine_label.grid(row=0, column=2, padx=(0, 16), pady=8)

        self.status_label = ctk.CTkLabel(
            self,
            text=CONNECTION_STATES["disconnected"],
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.status_label.grid(row=0, column=4, padx=(0, 20), pady=8)

    def set_connection_state(self, state: str) -> None:
        self.status_label.configure(text=CONNECTION_STATES.get(state, CONNECTION_STATES["disconnected"]))


class MainWindow(ctk.CTk):

    def __init__(self, display_name: str | None = None) -> None:
        super().__init__()
        self._display_name = display_name
        self.title("Vicky Consulting")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self._config = AppConfig()
        ctk.set_appearance_mode("dark" if self._config.settings.theme == "dark" else "light")

        self._conversation_service = ConversationService()

        knowledge_store = KnowledgeStore()
        self._knowledge_base = KnowledgeBase(knowledge_store)
        self._qa_log_service = QALogService(knowledge_store)
        self._connection_log_service = ConnectionLogService(knowledge_store)

        self._knowledge_base.sync_training_folder()

        settings = self._config.settings
        self._update_manager = UpdateManager(
            source=settings.update_source,
            endpoint_url=settings.update_endpoint,
            github_repo=settings.update_github_repo,
            channel=settings.update_channel,
        )
        self._update_dialog = None

        self._active_conversation_id: int | None = None
        self._current_view = "home"
        self._active_provider = None
        self._generating_job = None
        self._stop_requested = False
        self._current_stream_state: dict | None = None

        if self._display_name is None:
            self._show_login_overlay()
        else:
            self._build_layout()
            self._apply_initial_state()
            self._maybe_check_for_updates_on_startup()

    def _show_login_overlay(self) -> None:
        from ui.login_window import LoginOverlay

        self._login_overlay = LoginOverlay(self, on_complete=self._handle_login_complete)
        self._login_overlay.pack(fill="both", expand=True)

    def _handle_login_complete(self, display_name: str | None) -> None:
        self._display_name = display_name
        self._build_layout()
        self._apply_initial_state()
        self._maybe_check_for_updates_on_startup()

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = Sidebar(self, on_navigate=self._handle_navigate, display_name=self._display_name)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.content_container = ctk.CTkFrame(self, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_rowconfigure(1, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        self.content_header = ContentHeader(self.content_container)
        self.content_header.grid(row=0, column=0, sticky="ew")

        self.chat_panel = ChatPanel(
            self.content_container,
            on_send_message=self._handle_user_message,
            on_stop_generation=self._handle_stop_generation,
            on_attach_file=self._handle_attach_file,
            on_regenerate_message=self._handle_regenerate_message,
        )
        self.history_panel = HistoryPanel(
            self.content_container,
            on_select_conversation=self._handle_open_conversation,
            on_delete_conversation=self._handle_delete_conversation,
        )
        self.settings_page = SettingsPage(
            self.content_container,
            on_db_connection_change=self._handle_db_connection_result,
            knowledge_base=self._knowledge_base,
            qa_log_service=self._qa_log_service,
            connection_log_service=self._connection_log_service,
        )
        self.help_page = HelpPage(self.content_container)
        self.about_page = AboutPage(
            self.content_container,
            display_name=self._display_name,
            on_check_updates_now=self.check_for_updates_now,
        )

        self.chat_panel.grid(row=1, column=0, sticky="nsew")

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _apply_initial_state(self) -> None:
        self.sidebar.select("home")
        self.chat_panel.show_home(build_greeting(self._display_name))
        self.content_header.set_connection_state("disconnected")
        self.status_bar.set_ai_status(False)
        self.status_bar.set_db_status(False)
        self.status_bar.set_user("Administrador")

        if self._config.ai_credentials_locked:
            self._start_auto_connect_with_retry()

    def _maybe_check_for_updates_on_startup(self) -> None:
        self.after(1500, self._run_update_check)

    def _run_update_check(self, manual: bool = False) -> None:
        self._update_manager.check_for_updates(
            lambda info, err: self._handle_update_check_result(info, err, manual)
        )

    def _handle_update_check_result(self, update_info, error, manual: bool = False) -> None:
        self.after(0, lambda: self._apply_update_check_result(update_info, error, manual))

    def _apply_update_check_result(self, update_info, error, manual: bool = False) -> None:
        from datetime import datetime
        from tkinter import messagebox

        self._config.update(last_update_check=datetime.now().isoformat(timespec="seconds"))

        if error:
            get_logger().warning("Fallo al verificar actualizaciones: %s", error)
            if manual:
                messagebox.showerror(
                    "Buscar actualizaciones",
                    f"No se pudo verificar si hay una actualización disponible:\n\n{error}",
                )
            return

        if update_info is None:
            if manual:
                messagebox.showinfo(
                    "Buscar actualizaciones",
                    f"Ya tenés instalada la última versión (v{APP_VERSION}).",
                )
            return

        if self._update_dialog is not None:
            if manual:
                messagebox.showinfo(
                    "Buscar actualizaciones",
                    "Ya hay una actualización disponible esperando tu respuesta.",
                )
            return

        self._update_dialog = UpdateDialog(
            self,
            update_manager=self._update_manager,
            update_info=update_info,
            current_version=APP_VERSION,
            on_remind_later=self._handle_update_remind_later,
            on_ready_to_install=self._handle_update_ready_to_install,
        )

    def check_for_updates_now(self) -> None:
        self._run_update_check(manual=True)

    def _handle_update_remind_later(self) -> None:
        self._update_dialog = None

    def _handle_update_ready_to_install(self, installer_path: str) -> None:
        self._update_dialog = None
        get_logger().info("Instalando actualización descargada en: %s", installer_path)
        success, error = self._update_manager.install_update(installer_path, silent=False)

        if not success:
            get_logger().error("No se pudo iniciar el instalador: %s", error)
            return

        self.after(500, self.destroy)

    AUTO_CONNECT_INITIAL_DELAY_SECONDS = 10
    AUTO_CONNECT_DELAY_INCREMENT_SECONDS = 5

    def _start_auto_connect_with_retry(self) -> None:
        provider_cls = AI_PROVIDERS[AI_ENGINE_NAME]
        self.content_header.set_connection_state("connecting")
        self._auto_connect_attempt(AI_ENGINE_NAME, provider_cls, next_delay=self.AUTO_CONNECT_INITIAL_DELAY_SECONDS)

    def _auto_connect_attempt(self, engine_name: str, provider_cls, next_delay: int) -> None:
        if not self.winfo_exists():
            return

        settings = self._config.settings

        def worker() -> None:
            provider = provider_cls()
            connected, message = provider.connect(endpoint=settings.ai_endpoint, api_key=settings.ai_api_key)
            self.after(
                0,
                lambda: self._handle_auto_connect_result(engine_name, provider_cls, provider, connected, message, next_delay),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _handle_auto_connect_result(
        self, engine_name: str, provider_cls, provider, connected: bool, message: str, next_delay: int
    ) -> None:
        if not self.winfo_exists():
            return

        self._connection_log_service.log_ai_attempt(engine_name, connected, message)

        if connected:
            self._active_provider = provider
            self.content_header.set_connection_state("connected")
            self.status_bar.set_ai_status(True, engine_name)
            return

        self.content_header.set_connection_state("disconnected")
        self.status_bar.set_ai_status(False, engine_name)
        self.after(
            next_delay * 1000,
            lambda: self._auto_connect_attempt(engine_name, provider_cls, next_delay + self.AUTO_CONNECT_DELAY_INCREMENT_SECONDS),
        )
    def _hide_all_pages(self) -> None:
        self.chat_panel.grid_forget()
        self.history_panel.grid_forget()
        self.settings_page.grid_forget()
        self.help_page.grid_forget()
        self.about_page.grid_forget()

    def _handle_navigate(self, key: str) -> None:
        if self._current_view == "settings" and key != "settings":
            self.settings_page.save()

        self._current_view = key
        self._hide_all_pages()

        if key in ("home", "new_chat"):
            self._active_conversation_id = None
            self.chat_panel.grid(row=1, column=0, sticky="nsew")
            self.chat_panel.show_home(build_greeting(self._display_name))

        elif key == "history":
            self.history_panel.grid(row=1, column=0, sticky="nsew")
            grouped = self._conversation_service.list_grouped_conversations()
            self.history_panel.refresh(grouped)

        elif key == "settings":
            self.settings_page.grid(row=1, column=0, sticky="nsew")

        elif key == "help":
            self.help_page.grid(row=1, column=0, sticky="nsew")

        elif key == "about":
            self.about_page.grid(row=1, column=0, sticky="nsew")

    def _handle_delete_conversation(self, conversation_id: int) -> None:
        self._conversation_service.delete_conversation(conversation_id)

        if self._active_conversation_id == conversation_id:
            self._active_conversation_id = None

        grouped = self._conversation_service.list_grouped_conversations()
        self.history_panel.refresh(grouped)

    def _handle_open_conversation(self, conversation_id: int) -> None:
        self._active_conversation_id = conversation_id
        messages = self._conversation_service.get_conversation_messages(conversation_id)

        self._current_view = "new_chat"
        self._hide_all_pages()
        self.chat_panel.grid(row=1, column=0, sticky="nsew")
        self.chat_panel.load_conversation(messages)
        self.sidebar.select("history")

    def _handle_attach_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Adjuntar archivo",
            filetypes=[
                ("Archivos de texto", "*.txt *.md *.csv *.json *.log"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not file_path:
            return

        extension = Path(file_path).suffix.lower()
        if extension not in SUPPORTED_TEXT_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS))
            messagebox.showwarning(
                "Archivo no soportado",
                f"Tipo de archivo '{extension or 'sin extensión'}' no soportado todavía.\n\n"
                f"Por ahora se aceptan: {supported}",
                parent=self,
            )
            return

        self.chat_panel.input_bar.set_pending_attachment(file_path, Path(file_path).name)

    def _handle_db_connection_result(self, connected: bool, message: str) -> None:
        self.status_bar.set_db_status(connected, "SQL Server")

    def _handle_user_message(self, text: str, attachment_path: str | None = None) -> None:
        if self._active_conversation_id is None:
            conversation = self._conversation_service.start_new_conversation()
            self._active_conversation_id = conversation.id

        message = self._conversation_service.add_user_message(self._active_conversation_id, text)
        self.chat_panel.add_message(message)

        attachment_context = ""
        if attachment_path:
            attachment_context = self._consume_pending_attachment(attachment_path)

        self._stop_requested = False
        self._dispatch_ai_response(text, extra_context=attachment_context)

    def _consume_pending_attachment(self, attachment_path: str) -> str:
        try:
            filename, content = self._knowledge_base.read_ephemeral_attachment(attachment_path)
        except (UnsupportedFileTypeError, FileNotFoundError, OSError) as exc:
            note = self._conversation_service.add_assistant_message(
                self._active_conversation_id, f"⚠️ No se pudo adjuntar el archivo: {exc}"
            )
            self.chat_panel.add_message(note)
            return ""

        note = self._conversation_service.add_assistant_message(
            self._active_conversation_id,
            f"📎 Archivo «{filename}» adjuntado a este mensaje (se usa solo para responder esta "
            f"pregunta; no se guarda en la Base de Conocimiento).",
        )
        self.chat_panel.add_message(note)

        max_chars = 4000
        return f"--- Contenido de {filename} (adjuntado a este mensaje) ---\n{content[:max_chars]}"

    def _handle_regenerate_message(self, question: str) -> None:
        if self._active_conversation_id is None:
            return
        self._stop_requested = False
        self._dispatch_ai_response(question)

    def _dispatch_ai_response(self, question: str, extra_context: str = "") -> None:
        scored_matches = self._knowledge_base.search_with_scores(question)
        if scored_matches and not extra_context:
            top_score = scored_matches[0][0]
            threshold = top_score * 0.85
            candidates = [doc for score, doc in scored_matches if score >= threshold]
        else:
            candidates = []

        if len(candidates) >= 2:
            self._ask_clarification(candidates)
            return

        matches = candidates
        has_context = bool(matches) or bool(extra_context)

        if not has_context:
            self._refuse_out_of_scope(question)
            return

        self.chat_panel.set_generating(True)
        self.chat_panel.show_typing_indicator()

        source_filenames = ", ".join(m.filename for m in matches)
        kb_context = self._knowledge_base.build_context_snippet(matches)
        combined_context = "\n\n".join(part for part in (kb_context, extra_context) if part)
        augmented_text = (
            "Respondé ÚNICAMENTE usando la información de este contexto (documentos "
            "de la Base de Conocimiento / carpeta Training). Si la respuesta a la "
            "pregunta del usuario no está en este contexto, decí explícitamente que "
            "no tenés esa información en la Base de Conocimiento — no completes con "
            "tu conocimiento general, no inventes, y no busques en internet.\n\n"
            f"{combined_context}\n\nPregunta del usuario: {question}"
        )

        if self._active_provider is not None and self._active_provider.is_connected():
            self._start_real_ai_response(question, augmented_text, source_filenames)
        else:
            self._generating_job = self.after(
                900, lambda: self._finish_ai_response_placeholder(question, source_filenames)
            )

    _OUT_OF_SCOPE_MESSAGE = (
        "🔒 No tengo información sobre esto en la Base de Conocimiento (carpeta "
        "Training). Este asistente está configurado para responder solo con esos "
        "documentos — no uso conocimiento general ni busco en internet. Si es un "
        "tema válido, pedile a un administrador que agregue el documento "
        "correspondiente a la carpeta Training."
    )

    def _refuse_out_of_scope(self, question: str) -> None:
        message = self._conversation_service.add_assistant_message(
            self._active_conversation_id, self._OUT_OF_SCOPE_MESSAGE
        )
        self.chat_panel.add_message(message)
        self._qa_log_service.log(question, self._OUT_OF_SCOPE_MESSAGE, "Fuera de alcance", "")

    def _ask_clarification(self, tied_documents) -> None:
        options = [friendly_name(doc.filename) for doc in tied_documents]
        options_text = " o ".join(f"«{opt}»" for opt in options)
        clarification_text = (
            f"Encontré más de un procedimiento que podría aplicar: {options_text}. "
            f"¿Me confirmas a cuál te refieres? (por ejemplo, escribe el nombre del sistema)"
        )
        message = self._conversation_service.add_assistant_message(
            self._active_conversation_id, clarification_text
        )
        self.chat_panel.add_message(message)

    def _build_system_prompt(self) -> str:
        if self._display_name:
            return (
                f"Eres el Asistente IA de La Vianda. La persona que te está escribiendo "
                f"ya inició sesión en la aplicación con su cuenta de Microsoft y se llama "
                f"{self._display_name}. Si te pregunta su propio nombre, respondé con ese "
                f"nombre directamente — no digas que no tenés acceso a información personal, "
                f"porque esa información ya te la dieron acá."
            )
        return (
            "Eres el Asistente IA de La Vianda. No se pudo identificar el nombre de la "
            "persona que te está escribiendo en esta sesión. Si te pregunta su nombre, "
            "indicá amablemente que no lo tenés disponible en este momento."
        )

    def _start_real_ai_response(self, original_text: str, augmented_text: str, source_filenames: str) -> None:
        provider = self._active_provider
        conversation_id = self._active_conversation_id
        engine_name = provider.name
        system_prompt = self._build_system_prompt()

        bubble_holder: dict = {}
        accumulated_holder = {"text": ""}
        self._current_stream_state = {
            "bubble_holder": bubble_holder,
            "accumulated": accumulated_holder,
            "conversation_id": conversation_id,
        }

        def on_token(delta: str) -> None:
            accumulated_holder["text"] += delta

            def apply_on_ui_thread() -> None:
                if self._stop_requested or conversation_id != self._active_conversation_id:
                    return
                if "bubble" not in bubble_holder:
                    self.chat_panel.hide_typing_indicator()
                    bubble_holder["bubble"] = self.chat_panel.start_streaming_assistant_bubble()
                self.chat_panel.append_to_streaming_bubble(bubble_holder["bubble"], delta)

            self.after(0, apply_on_ui_thread)

        def worker() -> None:
            try:
                final_text = provider.send_message_stream(
                    augmented_text, on_token, should_stop=lambda: self._stop_requested, system_prompt=system_prompt
                )
                error_text = None
            except Exception as exc:
                final_text = None
                error_text = str(exc)

            self.after(
                0,
                lambda: self._finish_ai_response_real(
                    conversation_id, original_text, source_filenames, final_text, error_text, bubble_holder.get("bubble"), engine_name
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_ai_response_real(
        self,
        conversation_id: int,
        original_text: str,
        source_filenames: str,
        reply_text: str | None,
        error_text: str | None,
        streaming_bubble,
        engine_name: str,
    ) -> None:
        if self._stop_requested or conversation_id != self._active_conversation_id:
            return

        self.chat_panel.hide_typing_indicator()
        self.chat_panel.set_generating(False)
        self._current_stream_state = None

        if error_text:
            reply_text = f"⚠️ No se pudo obtener respuesta de {engine_name}: {error_text}"
            self.content_header.set_connection_state("disconnected")
            self.status_bar.set_ai_status(False, engine_name)
        elif reply_text is None:
            reply_text = ""

        message = self._conversation_service.add_assistant_message(conversation_id, reply_text)

        if streaming_bubble is not None:
            self.chat_panel.finalize_streaming_bubble(streaming_bubble, message)
        else:
            self.chat_panel.add_message(message)

        self._qa_log_service.log(original_text, reply_text, engine_name, source_filenames)

    def _finish_ai_response_placeholder(self, original_text: str, source_filenames: str = "") -> None:
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
        self._qa_log_service.log(original_text, reply_text, "Offline", source_filenames)

    def _handle_stop_generation(self) -> None:
        self._stop_requested = True
        if self._generating_job is not None:
            self.after_cancel(self._generating_job)
            self._generating_job = None
        self.chat_panel.hide_typing_indicator()
        self.chat_panel.set_generating(False)

        state = self._current_stream_state
        self._current_stream_state = None

        if state is not None and state["bubble_holder"].get("bubble") is not None:
            bubble = state["bubble_holder"]["bubble"]
            partial_text = state["accumulated"]["text"].strip()
            final_text = f"{partial_text}\n\n*(Respuesta interrumpida por el usuario)*" if partial_text else "(Generación detenida por el usuario)"
            message = self._conversation_service.add_assistant_message(state["conversation_id"], final_text)
            self.chat_panel.finalize_streaming_bubble(bubble, message)
            return

        stop_message = self._conversation_service.add_assistant_message(
            self._active_conversation_id, "(Generación detenida por el usuario)"
        )
        self.chat_panel.add_message(stop_message)
