"""
Panel central de la aplicación: pantalla de bienvenida, conversación
con burbujas, indicador de "escribiendo..." y caja de entrada de texto.

También incluye `HistoryPanel`, una vista preparada (sin base de datos
real todavía) que muestra cómo lucirá el historial de conversaciones
agrupado por fecha.
"""
import customtkinter as ctk

from models.message import Message, Sender
from ui import theme


# ---------------------------------------------------------------------- #
# Pantalla de bienvenida (sin conversación activa)
# ---------------------------------------------------------------------- #
class WelcomeScreen(ctk.CTkFrame):
    """Pantalla mostrada cuando todavía no existe una conversación."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, **kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")

        icon_label = ctk.CTkLabel(
            container,
            text="🤖",
            font=ctk.CTkFont(size=64),
        )
        icon_label.pack(pady=(0, 16))

        title_label = ctk.CTkLabel(
            container,
            text="Bienvenido al Asistente IA",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(pady=(0, 8))

        intro_label = ctk.CTkLabel(
            container,
            text="Puedo ayudarte con:",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        intro_label.pack(pady=(0, 4))

        items_text = "•  Inventario\n•  Ventas\n•  Clientes\n•  Facturación\n•  Reportes"
        items_label = ctk.CTkLabel(
            container,
            text=items_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_DARK,
            justify="left",
        )
        items_label.pack()


# ---------------------------------------------------------------------- #
# Burbuja de mensaje
# ---------------------------------------------------------------------- #
class MessageBubble(ctk.CTkFrame):
    """Burbuja individual de un mensaje (usuario o IA)."""

    def __init__(self, master, message: Message, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._message = message
        self._build_ui()

    def _build_ui(self) -> None:
        is_user = self._message.is_user
        bubble_bg = theme.BUBBLE_USER_BG if is_user else theme.BUBBLE_AI_BG
        text_color = theme.BUBBLE_USER_TEXT if is_user else theme.BUBBLE_AI_TEXT

        bubble = ctk.CTkFrame(self, fg_color=bubble_bg, corner_radius=theme.CORNER_RADIUS)
        # Alinea a la derecha (usuario) o a la izquierda (IA).
        bubble.pack(anchor="e" if is_user else "w", padx=12, pady=6)

        text_label = ctk.CTkLabel(
            bubble,
            text=self._message.content,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=text_color,
            wraplength=420,
            justify="left",
        )
        text_label.pack(padx=14, pady=(10, 2), anchor="w")

        time_label = ctk.CTkLabel(
            bubble,
            text=self._message.timestamp,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=text_color,
        )
        time_label.pack(padx=14, pady=(0, 8), anchor="e")


# ---------------------------------------------------------------------- #
# Indicador de "escribiendo..."
# ---------------------------------------------------------------------- #
class TypingIndicator(ctk.CTkFrame):
    """Indicador animado de que la IA está generando una respuesta."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._dot_count = 0
        self._job = None

        self.label = ctk.CTkLabel(
            self,
            text="La IA está escribiendo...",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        self.label.pack(side="left", padx=(12, 4), pady=6)

        self.dots_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.PRIMARY_BLUE,
        )
        self.dots_label.pack(side="left", pady=6)

    def start(self) -> None:
        self._animate()

    def stop(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _animate(self) -> None:
        self._dot_count = (self._dot_count % 3) + 1
        self.dots_label.configure(text=" " + ("● " * self._dot_count).strip())
        self._job = self.after(450, self._animate)


# ---------------------------------------------------------------------- #
# Caja de entrada de texto
# ---------------------------------------------------------------------- #
class ChatInputBar(ctk.CTkFrame):
    """Caja inferior de composición de mensajes."""

    def __init__(self, master, on_send=None, on_stop=None, **kwargs):
        super().__init__(master, fg_color=theme.SURFACE_WHITE, corner_radius=0, **kwargs)
        self._on_send = on_send
        self._on_stop = on_stop
        self._is_generating = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        self.attach_button = ctk.CTkButton(
            self,
            text="📎",
            width=36,
            fg_color="transparent",
            hover_color=theme.PRIMARY_BLUE_LIGHT,
            text_color=theme.TEXT_MUTED,
            command=self._attach_file,
        )
        self.attach_button.grid(row=0, column=0, padx=(12, 4), pady=10)

        self.text_entry = ctk.CTkTextbox(
            self,
            height=44,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.BACKGROUND_LIGHT,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
        )
        self.text_entry.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        self._set_placeholder()
        self.text_entry.bind("<FocusIn>", self._clear_placeholder)
        self.text_entry.bind("<KeyRelease>", self._on_key_release)
        self.text_entry.bind("<Return>", self._handle_return)
        self.text_entry.bind("<Shift-Return>", lambda e: None)  # deja el salto de línea normal

        self.dictate_button = ctk.CTkButton(
            self,
            text="🎤",
            width=36,
            fg_color="transparent",
            hover_color=theme.SURFACE_WHITE,
            text_color=theme.SIDEBAR_TEXT_DISABLED,
            state="disabled",
        )
        self.dictate_button.grid(row=0, column=2, padx=4, pady=10)

        self.send_button = ctk.CTkButton(
            self,
            text="Enviar",
            width=90,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_BLUE,
            hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._handle_send_or_stop,
        )
        self.send_button.grid(row=0, column=3, padx=(4, 12), pady=10)

    # ------------------------------------------------------------------ #
    # Placeholder manual (CTkTextbox no soporta placeholder nativo)
    # ------------------------------------------------------------------ #
    _PLACEHOLDER = "Pregúntame cualquier cosa sobre La Vianda..."

    def _set_placeholder(self) -> None:
        self.text_entry.insert("1.0", self._PLACEHOLDER)
        self.text_entry.configure(text_color=theme.TEXT_MUTED)
        self._showing_placeholder = True

    def _clear_placeholder(self, _event=None) -> None:
        if getattr(self, "_showing_placeholder", False):
            self.text_entry.delete("1.0", "end")
            self.text_entry.configure(text_color=theme.TEXT_DARK)
            self._showing_placeholder = False

    def _on_key_release(self, _event=None) -> None:
        pass

    def _handle_return(self, event) -> str:
        # Enter envía, Shift+Enter (manejado arriba) permite salto de línea.
        self._handle_send_or_stop()
        return "break"

    def _handle_send_or_stop(self) -> None:
        if self._is_generating:
            if self._on_stop:
                self._on_stop()
            return

        text = self.text_entry.get("1.0", "end").strip()
        if not text or getattr(self, "_showing_placeholder", False):
            return
        self.text_entry.delete("1.0", "end")
        if self._on_send:
            self._on_send(text)

    def _attach_file(self) -> None:
        # Funcionalidad deshabilitada por diseño en esta iteración.
        pass

    # ------------------------------------------------------------------ #
    # Control de estado mientras la IA responde
    # ------------------------------------------------------------------ #
    def set_generating(self, generating: bool) -> None:
        self._is_generating = generating
        if generating:
            self.text_entry.configure(state="disabled")
            self.send_button.configure(
                text="Detener", fg_color=theme.STATUS_RED, hover_color="#C93E42"
            )
        else:
            self.text_entry.configure(state="normal")
            self.send_button.configure(
                text="Enviar", fg_color=theme.PRIMARY_BLUE, hover_color=theme.PRIMARY_BLUE_HOVER
            )


# ---------------------------------------------------------------------- #
# Panel de conversación (bienvenida + burbujas + entrada)
# ---------------------------------------------------------------------- #
class ChatPanel(ctk.CTkFrame):
    """Contenedor principal: alterna entre bienvenida y conversación activa."""

    def __init__(self, master, on_send_message=None, on_stop_generation=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, **kwargs)
        self._on_send_message = on_send_message
        self._on_stop_generation = on_stop_generation
        self._typing_indicator: TypingIndicator | None = None
        self._has_conversation = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.welcome_screen = WelcomeScreen(self)
        self.welcome_screen.grid(row=0, column=0, sticky="nsew")

        self.messages_container = ctk.CTkScrollableFrame(
            self, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0
        )

        self.input_bar = ChatInputBar(
            self,
            on_send=self._handle_user_message,
            on_stop=self._handle_stop_requested,
        )

    # ------------------------------------------------------------------ #
    # Transición bienvenida <-> conversación
    # ------------------------------------------------------------------ #
    def start_new_conversation(self) -> None:
        """Limpia la vista actual y muestra un lienzo de chat vacío."""
        self._has_conversation = True
        self.welcome_screen.grid_forget()

        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._typing_indicator = None

        self.messages_container.grid(row=0, column=0, sticky="nsew")
        self.input_bar.grid(row=1, column=0, sticky="ew")

    def load_conversation(self, messages: list[Message]) -> None:
        """Restaura una conversación existente completa (todas sus burbujas)."""
        self._has_conversation = True
        self.welcome_screen.grid_forget()

        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._typing_indicator = None

        self.messages_container.grid(row=0, column=0, sticky="nsew")
        self.input_bar.grid(row=1, column=0, sticky="ew")

        for message in messages:
            bubble = MessageBubble(self.messages_container, message)
            bubble.pack(fill="x", padx=4, pady=2)
        self._scroll_to_bottom()

    def show_welcome(self) -> None:
        self._has_conversation = False
        self.messages_container.grid_forget()
        self.input_bar.grid_forget()
        self.welcome_screen.grid(row=0, column=0, sticky="nsew")

    # ------------------------------------------------------------------ #
    # Mensajes
    # ------------------------------------------------------------------ #
    def add_message(self, message: Message) -> None:
        if not self._has_conversation:
            self.start_new_conversation()
        bubble = MessageBubble(self.messages_container, message)
        bubble.pack(fill="x", padx=4, pady=2)
        self._scroll_to_bottom()

    def show_typing_indicator(self) -> None:
        if self._typing_indicator is None:
            self._typing_indicator = TypingIndicator(self.messages_container)
        self._typing_indicator.pack(anchor="w", padx=12, pady=4)
        self._typing_indicator.start()
        self._scroll_to_bottom()

    def hide_typing_indicator(self) -> None:
        if self._typing_indicator is not None:
            try:
                self._typing_indicator.stop()
                self._typing_indicator.pack_forget()
            except Exception:
                pass
            self._typing_indicator = None

    def _scroll_to_bottom(self) -> None:
        self.messages_container.update_idletasks()
        try:
            self.messages_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def set_generating(self, generating: bool) -> None:
        self.input_bar.set_generating(generating)

    # ------------------------------------------------------------------ #
    # Callbacks internos
    # ------------------------------------------------------------------ #
    def _handle_user_message(self, text: str) -> None:
        if self._on_send_message:
            self._on_send_message(text)

    def _handle_stop_requested(self) -> None:
        if self._on_stop_generation:
            self._on_stop_generation()


# ---------------------------------------------------------------------- #
# Panel de historial (interfaz preparada, sin base de datos real todavía)
# ---------------------------------------------------------------------- #
# ---------------------------------------------------------------------- #
# Panel de historial (datos reales desde ConversationService)
# ---------------------------------------------------------------------- #
class HistoryPanel(ctk.CTkScrollableFrame):
    """Vista de historial de conversaciones agrupadas por fecha (datos reales)."""

    def __init__(self, master, on_select_conversation=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._on_select_conversation = on_select_conversation

    def refresh(self, grouped_conversations) -> None:
        """
        Reconstruye la lista a partir de una estructura ya agrupada:
            [("Hoy", [Conversation, ...]), ("Ayer", [...]), ...]
        """
        for widget in self.winfo_children():
            widget.destroy()

        if not grouped_conversations:
            empty_label = ctk.CTkLabel(
                self,
                text="Todavía no hay conversaciones guardadas.",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
                text_color=theme.TEXT_MUTED,
            )
            empty_label.pack(padx=16, pady=24)
            return

        for group_label, conversations in grouped_conversations:
            group_title = ctk.CTkLabel(
                self,
                text=group_label,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
                text_color=theme.TEXT_MUTED,
            )
            group_title.pack(anchor="w", padx=16, pady=(16, 4))

            for conversation in conversations:
                self._add_conversation_row(conversation)

    def _add_conversation_row(self, conversation) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)

        time_text = ""
        try:
            from datetime import datetime as _dt

            time_text = _dt.fromisoformat(conversation.created_at).strftime("%H:%M")
        except ValueError:
            pass

        item_button = ctk.CTkButton(
            row,
            text=f"💬  {conversation.title}",
            anchor="w",
            fg_color="transparent",
            hover_color=theme.PRIMARY_BLUE_LIGHT,
            text_color=theme.TEXT_DARK,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            command=lambda cid=conversation.id: self._handle_select(cid),
        )
        item_button.pack(side="left", fill="x", expand=True)

        meta_label = ctk.CTkLabel(
            row,
            text=f"{time_text}  ·  {conversation.message_count} msj",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
        )
        meta_label.pack(side="right", padx=(4, 8))

    def _handle_select(self, conversation_id: int) -> None:
        if self._on_select_conversation:
            self._on_select_conversation(conversation_id)
