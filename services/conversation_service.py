"""
Servicio de Conversaciones.

Orquesta el `ConversationStore` (persistencia SQLite) y agrega la
lógica de negocio que la UI necesita: crear conversaciones, enviar
mensajes, generar el título automático a partir del primer mensaje, y
agrupar el historial por "Hoy" / "Ayer" / fecha.
"""
from datetime import date, datetime, timedelta
from typing import List, Tuple

from database.conversation_store import ConversationStore
from models.conversation import Conversation
from models.message import Message, Sender

TITLE_MAX_LENGTH = 48


class ConversationService:
    """Punto único de acceso a la lógica de conversaciones para la UI."""

    def __init__(self, store: ConversationStore | None = None) -> None:
        self._store = store or ConversationStore()

    # ------------------------------------------------------------------ #
    # Ciclo de vida de una conversación
    # ------------------------------------------------------------------ #
    def start_new_conversation(self) -> Conversation:
        """Crea una conversación nueva con un ID propio (no borra las anteriores)."""
        return self._store.create_conversation()

    def get_conversation_messages(self, conversation_id: int) -> List[Message]:
        return self._store.get_messages(conversation_id)

    # ------------------------------------------------------------------ #
    # Envío de mensajes
    # ------------------------------------------------------------------ #
    def add_user_message(self, conversation_id: int, text: str) -> Message:
        message = self._store.add_message(conversation_id, Sender.USER.value, text)
        self._maybe_set_title(conversation_id, text)
        return message

    def add_assistant_message(self, conversation_id: int, text: str) -> Message:
        return self._store.add_message(conversation_id, Sender.ASSISTANT.value, text)

    def _maybe_set_title(self, conversation_id: int, first_user_text: str) -> None:
        """La primera vez que el usuario escribe, ese texto se vuelve el título."""
        conversation = self._store.get_conversation(conversation_id)
        if conversation is None:
            return
        # message_count == 1 significa que este es el primer mensaje registrado.
        if conversation.message_count == 1 and conversation.title == "Nueva conversación":
            self._store.update_title(conversation_id, self._truncate_title(first_user_text))

    @staticmethod
    def _truncate_title(text: str, max_length: int = TITLE_MAX_LENGTH) -> str:
        clean = " ".join(text.strip().split())
        if len(clean) <= max_length:
            return clean or "Nueva conversación"
        return clean[:max_length].rsplit(" ", 1)[0] + "..."

    # ------------------------------------------------------------------ #
    # Historial agrupado (Hoy / Ayer / fecha)
    # ------------------------------------------------------------------ #
    def list_grouped_conversations(self) -> List[Tuple[str, List[Conversation]]]:
        """
        Retorna el historial agrupado por fecha, ej.:
            [("Hoy", [conv1, conv2]), ("Ayer", [conv3]), ("10/07/2026", [conv4])]

        Solo incluye conversaciones que ya tienen al menos un mensaje
        (una conversación recién creada por "Nuevo Chat" pero vacía
        todavía no aparece en el historial).
        """
        all_conversations = [c for c in self._store.get_all_conversations() if c.message_count > 0]

        today = date.today()
        yesterday = today - timedelta(days=1)

        groups: List[Tuple[str, List[Conversation]]] = []
        current_label = None
        current_items: List[Conversation] = []

        for conversation in all_conversations:
            conv_date = self._parse_date(conversation.created_at)
            if conv_date == today:
                label = "Hoy"
            elif conv_date == yesterday:
                label = "Ayer"
            else:
                label = conv_date.strftime("%d/%m/%Y")

            if label != current_label:
                if current_label is not None:
                    groups.append((current_label, current_items))
                current_label = label
                current_items = []
            current_items.append(conversation)

        if current_label is not None:
            groups.append((current_label, current_items))

        return groups

    @staticmethod
    def _parse_date(iso_timestamp: str) -> date:
        try:
            return datetime.fromisoformat(iso_timestamp).date()
        except ValueError:
            return date.today()
