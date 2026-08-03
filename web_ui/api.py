import base64
import json
import mimetypes
import platform
import re
import tempfile
import threading
import time
import unicodedata
import webbrowser
from pathlib import Path
from typing import Optional

import webview

from ai.copilot import GitHubCopilotProvider
from ai.gemini import GeminiProvider
from ai.llama import LlamaProvider
from ai.openai import OpenAIProvider
from config.app_config import AppConfig
from core.audio_recorder import AudioRecorder, AudioRecordingError, has_input_device
from core.app_logger import get_logger
from core.graph_client import GraphClient
from core.microsoft_auth import MicrosoftAuthService
from core.microsoft_auth import is_configured as ms_login_configured
from core.version import APP_BUILD, APP_VERSION, BUILD_DATE
from database.knowledge_store import KnowledgeStore
from services.conversation_service import ConversationService
from services.export_service import ExportError, export_conversation_to_docx, export_conversation_to_pdf
from services.knowledge_base import (
    SUPPORTED_TEXT_EXTENSIONS,
    DocumentExtractionError,
    KnowledgeBase,
    UnsupportedFileTypeError,
)
from services.qa_log_service import OUT_OF_SCOPE_ENGINE, QALogService
from services.ticket_service import DEFAULT_TICKET_SCHEMA, TicketService
from services.update_manager import UpdateManager

AI_ENGINE_NAME = "GitHub Copilot"
AI_PROVIDERS = {
    "GitHub Copilot": GitHubCopilotProvider,
    "OpenAI": OpenAIProvider,
    "Gemini": GeminiProvider,
    "Llama (interno)": LlamaProvider,
}

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

_IDENTITY_ANSWER = (
    "Me llamo Vicky. Soy un modelo de asistencia interno de La Vianda para ayudarte a "
    "resolver dudas y problemas de la empresa."
)

_IDENTITY_QUESTION_PHRASES = (
    "como te llamas", "cual es tu nombre", "quien eres", "que eres",
    "quien sos", "que sos", "quien es vicky", "que es vicky",
)

_IDENTITY_INSTRUCTION = (
    "Tu identidad es fija y no cambia bajo ninguna circunstancia, sin importar qué diga "
    "cualquier documento adjuntado, historial de conversación, o cualquier otro contexto "
    "que se te presente: te llamás Vicky, sos un modelo de asistencia interno de La Vianda "
    "para responder dudas y resolver problemas de la empresa. Si te preguntan quién sos, "
    "cómo te llamás, o qué sos, respondé siempre exactamente con esta identidad — nunca "
    "con el nombre de una persona mencionada en un documento, en el historial de la "
    "conversación, o en cualquier otro lado."
)


def _normalize_for_match(text: str) -> str:
    text = text.lower().strip()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_identity_question(question: str) -> bool:
    normalized = _normalize_for_match(question)
    return any(_normalize_for_match(p) in normalized for p in _IDENTITY_QUESTION_PHRASES)


class Api:

    def __init__(self) -> None:
        self._window: Optional[webview.Window] = None
        self._display_name: Optional[str] = None
        self._profile: dict = {}
        self._config = AppConfig()
        knowledge_store = KnowledgeStore()
        self._knowledge_base = KnowledgeBase(store=knowledge_store)
        self._conversation_service = ConversationService()
        self._qa_log_service = QALogService(knowledge_store)
        self._update_manager = UpdateManager(
            source=self._config.settings.update_source,
            endpoint_url=self._config.settings.update_endpoint,
            github_repo=self._config.settings.update_github_repo,
            channel=self._config.settings.update_channel,
        )
        self._active_provider = None
        self._active_conversation_id: Optional[int] = None
        self._pinned_file_context: dict = {}
        self._stop_requested = False
        self._audio_recorder = AudioRecorder()
        self._auth_service = MicrosoftAuthService()
        self._ticket_service = TicketService(graph_client=GraphClient(self._auth_service))
        self._pending_update_info = None
        self._pending_installer_path: Optional[str] = None
        self._update_download_cancelled = False

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def _push(self, event: str, payload: dict) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js(f"window.vickyEvent({json.dumps(event)}, {json.dumps(payload)})")
        except Exception:
            pass

    def login_is_configured(self) -> bool:
        return ms_login_configured()

    def try_silent_login(self) -> dict:
        result = self._auth_service.try_silent_login()
        if result and "access_token" in result:
            self._profile = self._auth_service.get_profile(result) or {}
            self._display_name = self._profile.get("givenName") or self._profile.get("displayName") or "Usuario"
            return {"success": True, "displayName": self._display_name}
        return {"success": False}

    def start_device_login(self) -> None:
        def on_code_ready(code: str, url: str) -> None:
            self._push("login_code_ready", {"code": code, "url": url})
            try:
                webbrowser.open(url)
            except Exception as exc:
                get_logger().warning("No se pudo abrir el navegador automáticamente: %s", exc)

        def worker() -> None:
            success, result, message = self._auth_service.login_with_device_code(on_code_ready)
            if success and result:
                self._profile = self._auth_service.get_profile(result) or {}
                self._display_name = self._profile.get("givenName") or self._profile.get("displayName") or "Usuario"
                self._push("login_complete", {"success": True, "displayName": self._display_name})
            else:
                self._push("login_complete", {"success": False, "message": message})

        threading.Thread(target=worker, daemon=True).start()

    def get_profile(self) -> dict:
        """
        Perfil de la cuenta logueada para el panel desplegable de la barra
        lateral. Si es sesión invitada, devuelve solo isGuest=True.
        """
        if not self._profile:
            return {"isGuest": True}
        return {
            "isGuest": False,
            "displayName": self._profile.get("displayName") or self._display_name or "Usuario",
            "email": self._profile.get("email") or "",
            "jobTitle": self._profile.get("jobTitle") or "",
            "department": self._profile.get("department") or "",
            "officeLocation": self._profile.get("officeLocation") or "",
        }

    def logout(self) -> dict:
        self._auth_service.logout()
        self._display_name = None
        self._profile = {}
        return {"success": True}

    def continue_as_guest(self) -> dict:
        self._display_name = None
        self._profile = {}
        return {"success": True, "displayName": None}

    def start_new_conversation(self) -> dict:
        conversation = self._conversation_service.start_new_conversation()
        self._active_conversation_id = conversation.id
        return {"id": conversation.id, "title": conversation.title}

    def get_conversation_messages(self, conversation_id: int) -> list:
        self._active_conversation_id = conversation_id
        self._update_file_context_state()
        messages = self._conversation_service.get_conversation_messages(conversation_id)
        return [self._serialize_message(m) for m in messages]

    @staticmethod
    def _serialize_message(message) -> dict:
        return {
            "id": message.id,
            "content": message.content,
            "isUser": message.is_user,
            "timestamp": message.timestamp,
        }

    def _update_file_context_state(self) -> None:
        pinned = self._pinned_file_context.get(self._active_conversation_id)
        self._push("file_context_state", {"active": bool(pinned), "enabled": bool(pinned)})

    def send_message(self, text: str, attachment_path: Optional[str] = None) -> dict:
        if self._active_conversation_id is None:
            conversation = self._conversation_service.start_new_conversation()
            self._active_conversation_id = conversation.id

        conversation_id = self._active_conversation_id
        user_message = self._conversation_service.add_user_message(conversation_id, text)
        self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(user_message)})
        self._push("generation_started", {"conversationId": conversation_id})

        threading.Thread(
            target=self._process_attachment_and_dispatch,
            args=(conversation_id, text, attachment_path),
            daemon=True,
        ).start()

        return {"conversationId": conversation_id}

    def _process_attachment_and_dispatch(self, conversation_id: int, text: str, attachment_path: Optional[str]) -> None:
        extra_context = ""
        image_base64 = None
        image_mime_type = None

        if attachment_path:
            extension = Path(attachment_path).suffix.lower()
            if extension in SUPPORTED_IMAGE_EXTENSIONS:
                image_base64, image_mime_type = self._consume_pending_image(attachment_path, conversation_id)
            else:
                extra_context = self._consume_pending_attachment(attachment_path, conversation_id)
        else:
            pinned = self._pinned_file_context.get(conversation_id)
            if pinned:
                extra_context = (
                    f"--- Contenido de {pinned['filename']} (archivo fijado en esta conversación) ---\n"
                    f"{pinned['content']}"
                )

        self._dispatch_ai_response(conversation_id, text, extra_context, image_base64, image_mime_type)

    def _consume_pending_attachment(self, attachment_path: str, conversation_id: int) -> str:
        try:
            filename, content = self._knowledge_base.read_ephemeral_attachment(attachment_path)
        except (UnsupportedFileTypeError, DocumentExtractionError, FileNotFoundError, OSError) as exc:
            note = self._conversation_service.add_assistant_message(conversation_id, f"⚠️ No se pudo adjuntar el archivo: {exc}")
            self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(note)})
            return ""

        truncated = content[:4000]
        self._pinned_file_context[conversation_id] = {"filename": filename, "content": truncated}
        self._update_file_context_state()

        note = self._conversation_service.add_assistant_message(
            conversation_id,
            f"📎 Archivo «{filename}» fijado en esta conversación — te puedo seguir respondiendo "
            f"preguntas sobre él sin que lo vuelvas a adjuntar. No se guarda en la Base de "
            f"Conocimiento. Tocá el 📌 al lado de adjuntar cuando quieras dejarlo de lado.",
        )
        self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(note)})
        return f"--- Contenido de {filename} (adjuntado a este mensaje) ---\n{truncated}"

    def _consume_pending_image(self, attachment_path: str, conversation_id: int) -> tuple:
        path = Path(attachment_path)
        try:
            image_bytes = path.read_bytes()
        except OSError as exc:
            note = self._conversation_service.add_assistant_message(conversation_id, f"⚠️ No se pudo adjuntar la imagen: {exc}")
            self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(note)})
            return None, None

        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        note = self._conversation_service.add_assistant_message(conversation_id, f"🖼️ Imagen «{path.name}» adjuntada a este mensaje.")
        self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(note)})
        return encoded, mime_type

    def toggle_file_context(self, confirmed: bool) -> dict:
        conversation_id = self._active_conversation_id
        pinned = self._pinned_file_context.get(conversation_id)
        if not pinned:
            return {"active": False}

        if not confirmed:
            return {"active": True, "filename": pinned["filename"]}

        self._pinned_file_context.pop(conversation_id, None)
        self._update_file_context_state()
        note = self._conversation_service.add_assistant_message(
            conversation_id, f"👍 Listo, dejo de lado «{pinned['filename']}». Si querés preguntar de nuevo sobre él, volvé a adjuntarlo."
        )
        self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(note)})
        return {"active": False}

    def stop_generation(self) -> None:
        self._stop_requested = True

    def _build_system_prompt(self) -> str:
        if self._display_name:
            return (
                f"{_IDENTITY_INSTRUCTION} La persona que te está escribiendo ya inició sesión "
                f"en la aplicación con su cuenta de Microsoft y se llama {self._display_name}. "
                f"Si te pregunta el nombre DE ELLA (no el tuyo), respondé con ese nombre "
                f"directamente — no digas que no tenés acceso a información personal, porque "
                f"esa información ya te la dieron acá."
            )
        return (
            f"{_IDENTITY_INSTRUCTION} No se pudo identificar el nombre de la persona que te "
            "está escribiendo en esta sesión. Si te pregunta el nombre DE ELLA (no el tuyo), "
            "indicá amablemente que no lo tenés disponible en este momento."
        )

    @staticmethod
    def _build_augmented_text(question: str, kb_context: str, extra_context: str) -> str:
        if extra_context:
            return (
                "Tenés acceso al contenido completo de un documento que el usuario adjuntó a esta "
                "conversación para analizarlo (aparece más abajo). Respondé sus preguntas sobre ese "
                "documento: podés citar datos exactos, resumir, comparar, y también razonar o dar tu "
                "análisis/opinión cuando te lo pidan — dejá claro cuándo algo es tu interpretación y "
                "no un dato literal del texto. Si la pregunta no tiene ninguna relación con este "
                "documento ni con la conversación, decí que no encontrás esa información en el "
                "documento adjuntado. Si te preguntan sobre vos mismo, respondé con tu identidad fija "
                "(Vicky) — nunca con el nombre de alguna persona que aparezca dentro del documento.\n\n"
                f"{extra_context}\n\nPregunta del usuario: {question}"
            )
        if kb_context:
            return (
                "Respondé ÚNICAMENTE usando la información de este contexto (documentos de la "
                "Base de Conocimiento / carpeta Training). Si la respuesta no está en este contexto, "
                "decí explícitamente que no tenés esa información en la Base de Conocimiento — no "
                "completes con tu conocimiento general, no inventes, y no busques en internet.\n\n"
                f"{kb_context}\n\nPregunta del usuario: {question}"
            )
        return question

    def _dispatch_ai_response(
        self, conversation_id: int, question: str, extra_context: str, image_base64, image_mime_type
    ) -> None:
        if _is_identity_question(question):
            self._qa_log_service.log(question, _IDENTITY_ANSWER, "Identidad fija", "")
            message = self._conversation_service.add_assistant_message(conversation_id, _IDENTITY_ANSWER)
            self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(message)})
            self._push("generation_finished", {"conversationId": conversation_id})
            return

        embed_fn = self._active_provider.embed if self._active_provider is not None else None
        scored_matches = self._knowledge_base.search_with_scores(question, embed_fn=embed_fn)
        candidates = []
        if scored_matches and not extra_context:
            threshold = scored_matches[0][0] * 0.85
            candidates = [doc for score, doc in scored_matches if score >= threshold]

        if len(candidates) >= 2:
            self._push("clarification_needed", {
                "conversationId": conversation_id,
                "options": [{"filename": c.filename} for c in candidates],
            })
            self._push("generation_finished", {"conversationId": conversation_id})
            return

        has_context = bool(candidates) or bool(extra_context) or bool(image_base64)
        if not has_context:
            reply = (
                "🔒 No tengo información sobre esto en la Base de Conocimiento (carpeta "
                "Training). Este asistente está configurado para responder solo con esos "
                "documentos — no uso conocimiento general ni busco en internet. Si es un "
                "tema válido, pedile a un administrador que agregue el documento "
                "correspondiente a la carpeta Training."
            )
            self._qa_log_service.log(question, reply, OUT_OF_SCOPE_ENGINE, "")
            message = self._conversation_service.add_assistant_message(conversation_id, reply)
            self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(message)})
            self._push("generation_finished", {"conversationId": conversation_id})
            return

        source_filenames = ", ".join(m.filename for m in candidates)
        kb_context = self._knowledge_base.build_context_snippet(candidates)
        augmented_text = self._build_augmented_text(question, kb_context, extra_context)

        if self._active_provider is None or not self._active_provider.is_connected():
            reply = (
                "🔌 No hay conexión con la IA en este momento. Conectate desde Configuración "
                "para poder responder esta pregunta."
            )
            message = self._conversation_service.add_assistant_message(conversation_id, reply)
            self._push("message_added", {"conversationId": conversation_id, "message": self._serialize_message(message)})
            self._push("generation_finished", {"conversationId": conversation_id})
            return

        self._stop_requested = False

        provider = self._active_provider
        system_prompt = self._build_system_prompt()
        history = self._build_recent_history(conversation_id)
        accumulated = {"text": ""}

        def on_token(delta: str) -> None:
            accumulated["text"] += delta
            self._push("token", {"conversationId": conversation_id, "delta": delta})

        try:
            final_text = provider.send_message_stream(
                augmented_text, on_token, should_stop=lambda: self._stop_requested,
                system_prompt=system_prompt, history=history,
                image_base64=image_base64, image_mime_type=image_mime_type,
            )
            error_text = None
        except Exception as exc:
            final_text = None
            error_text = str(exc)

        if self._stop_requested and accumulated["text"]:
            final_text = accumulated["text"]
            error_text = None

        if error_text:
            reply_text = f"⚠️ Ocurrió un error al generar la respuesta: {error_text}"
        else:
            reply_text = final_text or accumulated["text"]

        message = self._conversation_service.add_assistant_message(conversation_id, reply_text)
        self._qa_log_service.log(question, reply_text, provider.name, source_filenames)
        self._push("generation_finished", {"conversationId": conversation_id, "message": self._serialize_message(message)})

        all_messages = self._conversation_service.get_conversation_messages(conversation_id)
        user_message_count = sum(1 for m in all_messages if m.is_user)
        if user_message_count == 1 and not error_text:
            self._generate_conversation_title(conversation_id, question, reply_text, provider)

    def _generate_conversation_title(self, conversation_id: int, question: str, answer: str, provider) -> None:
        prompt = (
            "Resumí de qué trata este intercambio en un título corto, de máximo 6 palabras, "
            "sin comillas ni punto final, en español neutro. Respondé ÚNICAMENTE con el "
            f"título, nada más.\n\nUsuario: {question}\nAsistente: {answer[:500]}"
        )
        try:
            title = provider.send_message(prompt)
        except Exception:
            return

        title = (title or "").strip().strip('"').strip("'").strip(".")
        if not title:
            return

        self._conversation_service.set_title(conversation_id, title)
        self._push("conversation_title_updated", {"conversationId": conversation_id, "title": title})

    def _build_recent_history(self, conversation_id: int) -> list:
        messages = self._conversation_service.get_conversation_messages(conversation_id)
        if not messages:
            return []
        previous = messages[:-1]
        recent = previous[-10:]
        return [{"role": "user" if m.is_user else "assistant", "content": m.content} for m in recent]

    def regenerate_message(self, question: str) -> dict:
        if self._active_conversation_id is None:
            return {"ok": False}
        conversation_id = self._active_conversation_id
        threading.Thread(
            target=self._dispatch_ai_response,
            args=(conversation_id, question, "", None, None),
            daemon=True,
        ).start()
        return {"ok": True}

    def edit_message(self, conversation_id: int, message_id: int, new_text: str) -> dict:
        self._conversation_service.edit_user_message(conversation_id, message_id, new_text)
        self._push("conversation_reset", {"conversationId": conversation_id})
        self._push("generation_started", {"conversationId": conversation_id})

        threading.Thread(
            target=self._dispatch_after_edit,
            args=(conversation_id, new_text),
            daemon=True,
        ).start()
        return {"ok": True}

    def _dispatch_after_edit(self, conversation_id: int, new_text: str) -> None:
        pinned = self._pinned_file_context.get(conversation_id)
        extra_context = ""
        if pinned:
            extra_context = (
                f"--- Contenido de {pinned['filename']} (archivo fijado en esta conversación) ---\n"
                f"{pinned['content']}"
            )
        self._dispatch_ai_response(conversation_id, new_text, extra_context, None, None)

    def list_grouped_conversations(self) -> list:
        grouped = self._conversation_service.list_grouped_conversations()
        return [
            {"group": label, "conversations": [{"id": c.id, "title": c.title} for c in convs]}
            for label, convs in grouped
        ]

    def delete_conversation(self, conversation_id: int) -> None:
        self._conversation_service.delete_conversation(conversation_id)
        self._pinned_file_context.pop(conversation_id, None)
        if self._active_conversation_id == conversation_id:
            self._active_conversation_id = None

    def export_conversation(self, conversation_id: int, title: str) -> dict:
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", title or "conversacion").strip() or "conversacion"
        try:
            result = self._window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename=f"{safe_name}.docx",
                file_types=("Documento Word (*.docx)", "PDF (*.pdf)"),
            )
        except Exception as exc:
            return {"ok": False, "error": f"No se pudo abrir el diálogo de guardado: {exc}"}
        if not result:
            return {"ok": False}

        file_path = Path(result if isinstance(result, str) else result[0])
        messages = self._conversation_service.get_conversation_messages(conversation_id)
        try:
            if file_path.suffix.lower() == ".pdf":
                export_conversation_to_pdf(title, messages, file_path)
            else:
                export_conversation_to_docx(title, messages, file_path)
        except ExportError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(file_path)}

    def get_settings(self) -> dict:
        settings = self._config.settings
        return {
            "checkUpdatesOnStartup": settings.check_updates_on_startup,
            "silentUpdatesEnabled": settings.silent_updates_enabled,
        }

    def update_setting(self, key: str, value) -> None:
        mapping = {"checkUpdatesOnStartup": "check_updates_on_startup", "silentUpdatesEnabled": "silent_updates_enabled"}
        field = mapping.get(key)
        if field:
            self._config.update(**{field: value})

    def attach_file(self) -> dict:
        supported = sorted(SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS)
        pattern = ";".join(f"*{ext}" for ext in supported)
        try:
            result = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                file_types=(f"Documentos e imágenes soportados ({pattern})", "Todos los archivos (*.*)"),
            )
        except Exception as exc:
            return {"ok": False, "error": f"No se pudo abrir el diálogo de archivos: {exc}"}
        if not result:
            return {"ok": False}

        file_path = result[0] if isinstance(result, (list, tuple)) else result
        return self._validate_attachment(file_path)

    def _validate_attachment(self, file_path: str) -> dict:
        extension = Path(file_path).suffix.lower()
        is_image = extension in SUPPORTED_IMAGE_EXTENSIONS
        is_document = extension in SUPPORTED_TEXT_EXTENSIONS
        if not is_image and not is_document:
            return {"ok": False, "error": f"Tipo de archivo '{extension}' no soportado."}

        if is_image and self._active_provider is not None and not self._active_provider.supports_vision():
            return {"ok": False, "error": f"{self._active_provider.name} no soporta imágenes todavía."}

        return {"ok": True, "path": file_path, "name": Path(file_path).name}

    def attach_file_from_bytes(self, filename: str, base64_data: str) -> dict:
        extension = Path(filename).suffix.lower()
        if extension not in (SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS):
            return {"ok": False, "error": f"Tipo de archivo '{extension}' no soportado."}

        try:
            raw_bytes = base64.b64decode(base64_data)
        except Exception as exc:
            return {"ok": False, "error": f"No se pudo leer el archivo soltado: {exc}"}

        tmp_dir = Path(tempfile.mkdtemp(prefix="vicky_dragdrop_"))
        tmp_path = tmp_dir / Path(filename).name
        try:
            tmp_path.write_bytes(raw_bytes)
        except OSError as exc:
            return {"ok": False, "error": f"No se pudo guardar el archivo temporal: {exc}"}

        return self._validate_attachment(str(tmp_path))

    def start_dictation(self) -> dict:
        if self._active_provider is None or not self._active_provider.supports_dictation():
            engine_name = self._active_provider.name if self._active_provider else "el motor actual"
            return {"ok": False, "error": f"{engine_name} no soporta transcripción de voz todavía."}
        try:
            self._audio_recorder.start()
        except AudioRecordingError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    def stop_dictation(self) -> dict:
        try:
            wav_path = self._audio_recorder.stop()
        except AudioRecordingError as exc:
            return {"ok": False, "error": str(exc)}

        provider = self._active_provider

        def worker() -> None:
            try:
                text = provider.transcribe_audio(str(wav_path))
            except Exception:
                text = None
            finally:
                try:
                    wav_path.unlink(missing_ok=True)
                except OSError:
                    pass
            self._push("dictation_result", {"text": text})

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True}

    def connect_ai_provider(self) -> dict:
        settings = self._config.settings
        engine_name = settings.ai_engine or AI_ENGINE_NAME
        provider_cls = AI_PROVIDERS.get(engine_name, GitHubCopilotProvider)
        provider = provider_cls()
        connected, message = provider.connect(endpoint=settings.ai_endpoint, api_key=settings.ai_api_key)
        if connected:
            self._active_provider = provider
        return {"connected": connected, "message": message, "engine": provider.name}

    def get_about_status(self) -> dict:
        connected = self._active_provider is not None and self._active_provider.is_connected()
        engine_name = self._active_provider.name if self._active_provider else (self._config.settings.ai_engine or "Sin configurar")
        return {
            "appName": "Vicky",
            "version": APP_VERSION,
            "build": APP_BUILD,
            "buildDate": BUILD_DATE,
            "displayName": self._display_name or "Invitado",
            "aiEngine": engine_name,
            "aiConnected": connected,
            "secureStorageAvailable": self._config.secure_storage_available,
            "microphoneDetected": has_input_device(),
            "lastUpdateCheck": self._config.settings.last_update_check or "Nunca",
            "operatingSystem": f"{platform.system()} {platform.release()}",
        }

    def build_diagnostics_text(self) -> str:
        status = self.get_about_status()
        lines = [
            "Vicky — información de diagnóstico",
            f"Versión: {status['version']} (build {status['build']}, {status['buildDate']})",
            f"Usuario: {status['displayName']}",
            f"Motor de IA: {status['aiEngine']} ({'conectado' if status['aiConnected'] else 'sin conexión'})",
            f"Llavero seguro: {'disponible' if status['secureStorageAvailable'] else 'modo de respaldo (texto plano)'}",
            f"Micrófono: {'detectado' if status['microphoneDetected'] else 'no detectado'}",
            f"Sistema operativo: {status['operatingSystem']}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tickets (SharePoint)
    # ------------------------------------------------------------------

    def preview_ticket_from_conversation(self, conversation_id: Optional[int] = None) -> dict:
        """
        Genera un BORRADOR de ticket a partir de la conversación actual —
        no sube nada todavía. El usuario ve los campos extraídos en la UI,
        puede corregirlos, y solo si confirma se llama a submit_ticket().
        """
        conversation_id = conversation_id or self._active_conversation_id
        if conversation_id is None:
            return {"ok": False, "error": "No hay una conversación activa."}

        messages = self._conversation_service.get_conversation_messages(conversation_id)
        source_text = "\n".join(f"{'Usuario' if m.is_user else 'Vicky'}: {m.content}" for m in messages[-20:])

        fields = self._ticket_service.extract_fields(self._active_provider, source_text)
        draft = self._ticket_service.build_draft(fields, source="chat")
        return {
            "ok": True,
            "fields": draft.fields,
            "missingRequired": draft.missing_required,
            "schema": DEFAULT_TICKET_SCHEMA,
        }

    def check_pending_email_tickets(self) -> dict:
        """
        Revisa el correo reciente y devuelve BORRADORES de ticket detectados
        (no sube nada). Pensado para que un admin los revise en una vista de
        'Tickets pendientes' y confirme uno por uno con submit_ticket().
        """
        settings = self._config.settings
        drafts = self._ticket_service.find_ticket_requests_in_email(
            self._active_provider,
            sender_filter=settings.ticket_email_sender_filter or None,
        )

        results = []
        for draft in drafts:
            if draft.error:
                return {"ok": False, "error": draft.error}
            results.append({
                "fields": draft.fields,
                "missingRequired": draft.missing_required,
                "emailMessageId": draft.email_message_id,
                "emailSubject": draft.email_subject,
                "emailFrom": draft.email_from,
            })
        return {"ok": True, "drafts": results, "schema": DEFAULT_TICKET_SCHEMA}

    def submit_ticket(self, fields: dict) -> dict:
        """
        Sube el ticket a la Lista de SharePoint. Se llama ÚNICAMENTE cuando
        el usuario confirma explícitamente en la UI los campos mostrados por
        preview_ticket_from_conversation() o check_pending_email_tickets()
        (editados o no) — nunca automáticamente.
        """
        settings = self._config.settings
        try:
            field_mapping = json.loads(settings.ticket_field_mapping or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "El mapeo de columnas de SharePoint configurado no es un JSON válido."}

        return self._ticket_service.submit_ticket(
            settings.ticket_sharepoint_site_id,
            settings.ticket_sharepoint_list_id,
            fields,
            field_mapping,
        )

    def get_ticket_settings(self) -> dict:
        settings = self._config.settings
        return {
            "siteId": settings.ticket_sharepoint_site_id,
            "listId": settings.ticket_sharepoint_list_id,
            "fieldMapping": settings.ticket_field_mapping,
            "emailSenderFilter": settings.ticket_email_sender_filter,
            "autoCheckEmail": settings.ticket_auto_check_email,
        }

    def update_ticket_settings(
        self, site_id: str = "", list_id: str = "", field_mapping: str = "",
        email_sender_filter: str = "", auto_check_email: bool = False,
    ) -> dict:
        try:
            json.loads(field_mapping or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "El mapeo de columnas debe ser un JSON válido, ej: {\"nombre_solicitante\": \"Title\"}"}

        self._config.update(
            ticket_sharepoint_site_id=site_id.strip(),
            ticket_sharepoint_list_id=list_id.strip(),
            ticket_field_mapping=field_mapping.strip() or "{}",
            ticket_email_sender_filter=email_sender_filter.strip(),
            ticket_auto_check_email=bool(auto_check_email),
        )
        return {"ok": True}

    def check_updates_now(self) -> None:
        import datetime

        def on_result(update_info, error) -> None:
            self._config.update(last_update_check=datetime.datetime.now().isoformat())
            if error:
                self._push("update_check_result", {"available": False, "error": error})
            elif update_info:
                self._pending_update_info = update_info
                self._push("update_check_result", {
                    "available": True, "version": update_info.version, "notes": update_info.release_notes,
                    "mandatory": update_info.mandatory,
                })
            else:
                self._push("update_check_result", {"available": False})

        self._update_manager.check_for_updates(on_result)

    def download_update_now(self) -> dict:
        """
        Descarga el instalador de la actualización detectada por
        check_updates_now(), con progreso vía eventos 'update_download_progress'
        y resultado final vía 'update_download_complete'. La verificación de
        integridad (firma o checksum) la hace UpdateManager antes de avisar éxito.
        """
        if self._pending_update_info is None:
            return {"ok": False, "error": "No hay una actualización detectada todavía. Buscá actualizaciones primero."}

        self._update_download_cancelled = False

        def on_progress(downloaded: int, total: int, speed: float, percent: float) -> None:
            self._push("update_download_progress", {
                "downloaded": downloaded, "total": total, "speedBytesPerSec": speed, "percent": percent,
            })

        def on_complete(success: bool, installer_path: Optional[str], error: Optional[str]) -> None:
            if success:
                self._pending_installer_path = installer_path
                self._push("update_download_complete", {"ok": True})
            else:
                self._push("update_download_complete", {"ok": False, "error": error})

        self._update_manager.download_update(
            self._pending_update_info, on_progress, on_complete,
            should_cancel=lambda: self._update_download_cancelled,
        )
        return {"ok": True}

    def cancel_update_download(self) -> None:
        self._update_download_cancelled = True

    def install_update_now(self) -> dict:
        """
        Lanza el instalador ya descargado y verificado. La app se cierra unos
        instantes después para que el instalador pueda reemplazar los archivos
        en uso — el instalador es quien vuelve a abrir la app al terminar.
        Se llama únicamente cuando el usuario confirma explícitamente en el
        modal de actualización, nunca automáticamente.
        """
        if not self._pending_installer_path:
            return {"ok": False, "error": "No hay un instalador descargado todavía."}

        settings = self._config.settings
        success, error = self._update_manager.install_update(
            self._pending_installer_path, silent=settings.silent_updates_enabled
        )
        if not success:
            return {"ok": False, "error": error}

        def close_soon() -> None:
            time.sleep(1.5)
            if self._window is not None:
                try:
                    self._window.destroy()
                except Exception:
                    pass

        threading.Thread(target=close_soon, daemon=True).start()
        return {"ok": True}
