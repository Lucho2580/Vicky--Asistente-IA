from datetime import date, datetime, timedelta
from typing import List, Tuple

from database.conversation_store import ConversationStore
from models.conversation import Conversation
from models.message import Message, Sender

TITLE_MAX_LENGTH = 48


class ConversationService:

    def __init__(self, store: ConversationStore | None = None) -> None:
        self._store = store or ConversationStore()

    def start_new_conversation(self) -> Conversation:
        return self._store.create_conversation()

    def get_conversation_messages(self, conversation_id: int) -> List[Message]:
        return self._store.get_messages(conversation_id)

    def delete_conversation(self, conversation_id: int) -> None:
        self._store.delete_conversation(conversation_id)

    def add_user_message(self, conversation_id: int, text: str) -> Message:
        message = self._store.add_message(conversation_id, Sender.USER.value, text)
        self._maybe_set_title(conversation_id, text)
        return message

    def edit_user_message(self, conversation_id: int, message_id: int, new_text: str) -> Message:
        self._store.delete_messages_from(conversation_id, message_id)
        return self.add_user_message(conversation_id, new_text)

    def add_assistant_message(self, conversation_id: int, text: str) -> Message:
        return self._store.add_message(conversation_id, Sender.ASSISTANT.value, text)

    def _maybe_set_title(self, conversation_id: int, first_user_text: str) -> None:
        conversation = self._store.get_conversation(conversation_id)
        if conversation is None:
            return
        if conversation.message_count == 1 and conversation.title == "Nueva conversación":
            self._store.update_title(conversation_id, self._truncate_title(first_user_text))

    def set_title(self, conversation_id: int, title: str) -> None:
        clean_title = self._truncate_title(title)
        self._store.update_title(conversation_id, clean_title)

    @staticmethod
    def _truncate_title(text: str, max_length: int = TITLE_MAX_LENGTH) -> str:
        clean = " ".join(text.strip().split())
        if len(clean) <= max_length:
            return clean or "Nueva conversación"
        return clean[:max_length].rsplit(" ", 1)[0] + "..."

    def list_grouped_conversations(self) -> List[Tuple[str, List[Conversation]]]:
        all_conversations = [c for c in self._store.get_all_conversations() if c.message_count > 0]

        groups: List[Tuple[str, List[Conversation]]] = []
        current_label = None
        current_items: List[Conversation] = []

        for conversation in all_conversations:
            conv_date = self._parse_date(conversation.created_at)
            label = self._group_label_for_date(conv_date)

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
    def _group_label_for_date(conv_date: date, today: date | None = None) -> str:
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        if conv_date == today:
            return "Hoy"
        if conv_date == yesterday:
            return "Ayer"
        if conv_date > week_ago:
            return "Últimos 7 días"
        if conv_date.year == today.year and conv_date.month == today.month:
            return "Este mes"
        return "Más antiguas"

    @staticmethod
    def _parse_date(iso_timestamp: str) -> date:
        try:
            return datetime.fromisoformat(iso_timestamp).date()
        except ValueError:
            return date.today()
