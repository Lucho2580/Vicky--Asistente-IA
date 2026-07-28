from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from models.message import Message, Sender
from ui import theme
from ui.assets_path import get_asset_path
from ui.markdown_blocks import render_markdown

BUBBLE_MAX_WIDTH = 420
_LOGO_PATH = get_asset_path("logo.png")
_LOGO_WATERMARK_PATH = get_asset_path("logo_watermark.png")


class HomeGreeting(ctk.CTkFrame):

    def __init__(
        self,
        master,
        greeting_text: str = "",
        subtitle_text: str = "¿En qué puedo ayudarte hoy?",
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, **kwargs)
        self._build_ui(greeting_text, subtitle_text)

    def _build_ui(self, greeting_text: str, subtitle_text: str) -> None:
        try:
            self._watermark_source = Image.open(_LOGO_WATERMARK_PATH).convert("RGBA")
            self._watermark_label = ctk.CTkLabel(self, text="")
            self._watermark_label.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._watermark_label.lower()
            self.bind("<Configure>", self._update_watermark, add="+")
        except Exception:
            self._watermark_source = None

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.42, anchor="center")

        try:
            icon_circle = ctk.CTkFrame(
                container, width=76, height=76, corner_radius=38, fg_color=theme.PRIMARY_RED_LIGHT
            )
            icon_circle.pack(pady=(0, 14))
            icon_circle.pack_propagate(False)
            logo_image = ctk.CTkImage(Image.open(_LOGO_PATH), size=(44, 44))
            ctk.CTkLabel(icon_circle, image=logo_image, text="").place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

        self.greeting_label = ctk.CTkLabel(
            container,
            text=greeting_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=26, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        self.greeting_label.pack(pady=(0, 6))

        self.subtitle_label = ctk.CTkLabel(
            container,
            text=subtitle_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        self.subtitle_label.pack()

    def _update_watermark(self, event=None) -> None:
        if not getattr(self, "_watermark_source", None):
            return
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 2 or height < 2:
            return

        if getattr(self, "_last_watermark_size", None) == (width, height):
            return
        self._last_watermark_size = (width, height)

        cover = self._make_cover_image(self._watermark_source, width, height)
        self._watermark_image = ctk.CTkImage(cover, size=(width, height))
        self._watermark_label.configure(image=self._watermark_image)

    @staticmethod
    def _make_cover_image(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
        img_ratio = image.width / image.height
        target_ratio = target_w / max(target_h, 1)
        if img_ratio > target_ratio:
            new_h = target_h
            new_w = max(int(new_h * img_ratio), 1)
        else:
            new_w = target_w
            new_h = max(int(new_w / img_ratio), 1)
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    def set_greeting(self, greeting_text: str) -> None:
        self.greeting_label.configure(text=greeting_text)


class MessageBubble(ctk.CTkFrame):

    def __init__(self, master, message: Message, on_regenerate=None, streaming: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._message = message
        self._on_regenerate = on_regenerate
        self._is_streaming = streaming
        self._stream_label = None
        self._content_frame = None
        self._footer = None
        self._regenerate_button = None
        self._build_ui()

    def _build_ui(self) -> None:
        is_user = self._message.is_user
        bubble_bg = theme.BUBBLE_USER_BG if is_user else theme.BUBBLE_AI_BG
        self._text_color = theme.BUBBLE_USER_TEXT if is_user else theme.BUBBLE_AI_TEXT
        self._is_user = is_user

        self._bubble = ctk.CTkFrame(self, fg_color=bubble_bg, corner_radius=theme.CORNER_RADIUS)
        self._bubble.pack(anchor="e" if is_user else "w", padx=12, pady=6)

        self._content_frame = ctk.CTkFrame(self._bubble, fg_color="transparent")
        self._content_frame.pack(padx=14, pady=(10, 2), anchor="w", fill="x")

        if self._is_streaming:
            self._stream_label = ctk.CTkLabel(
                self._content_frame,
                text="",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
                text_color=self._text_color,
                wraplength=BUBBLE_MAX_WIDTH,
                justify="left",
                anchor="w",
            )
            self._stream_label.pack(fill="x", anchor="w")
        else:
            render_markdown(self._content_frame, self._message.content, self._text_color, max_width=BUBBLE_MAX_WIDTH)

        self._footer = ctk.CTkFrame(self._bubble, fg_color="transparent")
        self._footer.pack(padx=14, pady=(0, 8), anchor="e", fill="x")
        self._footer.grid_columnconfigure(1, weight=1)

        self._time_label = ctk.CTkLabel(
            self._footer,
            text=self._message.timestamp,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=self._text_color,
        )
        self._time_label.grid(row=0, column=0, sticky="w")

        if not self._is_streaming:
            self._build_action_buttons()

    def _build_action_buttons(self) -> None:
        hover = theme.PRIMARY_RED_HOVER if self._is_user else theme.BORDER_LIGHT

        if not self._is_user and self._on_regenerate is not None:
            self._regenerate_button = ctk.CTkButton(
                self._footer,
                text="↻ Regenerar",
                width=80,
                height=20,
                fg_color="transparent",
                hover_color=hover,
                text_color=self._text_color,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
                command=self._handle_regenerate,
            )
            self._regenerate_button.grid(row=0, column=2, sticky="e", padx=(4, 0))

        self._copy_button = ctk.CTkButton(
            self._footer,
            text="Copiar",
            width=52,
            height=20,
            fg_color="transparent",
            hover_color=hover,
            text_color=self._text_color,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            command=self._copy_content,
        )
        self._copy_button.grid(row=0, column=3, sticky="e", padx=(4, 0))

    def _copy_content(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self._message.content)
        except Exception:
            pass

    def _handle_regenerate(self) -> None:
        if self._on_regenerate:
            self._on_regenerate()

    def append_streaming_text(self, delta: str) -> None:
        if self._stream_label is not None:
            self._stream_label.configure(text=self._stream_label.cget("text") + delta)

    def finalize(self, final_message: Message) -> None:
        self._message = final_message
        self._is_streaming = False

        if self._stream_label is not None:
            self._stream_label.destroy()
            self._stream_label = None

        for widget in self._content_frame.winfo_children():
            widget.destroy()
        render_markdown(self._content_frame, final_message.content, self._text_color, max_width=BUBBLE_MAX_WIDTH)

        self._time_label.configure(text=final_message.timestamp)
        self._build_action_buttons()


class TypingIndicator(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._dot_count = 0
        self._job = None

        self.label = ctk.CTkLabel(
            self,
            text="Pensando...",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        self.label.pack(side="left", padx=(12, 4), pady=6)

        self.dots_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.PRIMARY_RED,
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


class ChatInputBar(ctk.CTkFrame):

    _MIN_HEIGHT = 44
    _MAX_HEIGHT = 160

    def __init__(self, master, on_send=None, on_stop=None, on_attach=None, on_dictate_toggle=None, on_toggle_file_context=None, **kwargs):
        super().__init__(master, fg_color=theme.SURFACE_WHITE, corner_radius=0, **kwargs)
        self._on_send = on_send
        self._on_stop = on_stop
        self._on_attach = on_attach
        self._on_dictate_toggle = on_dictate_toggle
        self._on_toggle_file_context = on_toggle_file_context
        self._is_generating = False
        self._is_dictating = False
        self._pending_attachment_path: str | None = None
        self._current_height = self._MIN_HEIGHT
        self._resize_job = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(2, weight=1)

        self.attachment_chip = ctk.CTkFrame(
            self, fg_color=theme.BACKGROUND_LIGHT, corner_radius=theme.CORNER_RADIUS
        )
        self.attachment_label = ctk.CTkLabel(
            self.attachment_chip,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.attachment_label.pack(side="left", padx=(10, 4), pady=6)
        self.attachment_remove_button = ctk.CTkButton(
            self.attachment_chip,
            text="✕",
            width=22,
            height=22,
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.TEXT_MUTED,
            command=self.clear_pending_attachment,
        )
        self.attachment_remove_button.pack(side="left", padx=(0, 8), pady=6)

        self.attach_button = ctk.CTkButton(
            self,
            text="📎",
            width=44,
            height=40,
            corner_radius=theme.CORNER_RADIUS,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17),
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.TEXT_MUTED,
            command=self._attach_file,
        )
        self.attach_button.grid(row=1, column=0, padx=(12, 4), pady=10)

        self.file_context_button = ctk.CTkButton(
            self,
            text="📌",
            width=40,
            height=40,
            corner_radius=theme.CORNER_RADIUS,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=15),
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.SIDEBAR_TEXT_DISABLED,
            state="disabled",
            command=self._toggle_file_context,
        )
        self.file_context_button.grid(row=1, column=1, padx=4, pady=10)

        self.text_entry = ctk.CTkTextbox(
            self,
            height=self._MIN_HEIGHT,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.BACKGROUND_LIGHT,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            wrap="word",
        )
        self.text_entry.grid(row=1, column=2, padx=4, pady=10, sticky="ew")
        self._set_placeholder()
        self.text_entry.bind("<FocusIn>", self._clear_placeholder)
        self.text_entry.bind("<KeyRelease>", self._on_key_release)
        self.text_entry.bind("<Return>", self._handle_return)
        self.text_entry.bind("<Shift-Return>", lambda e: None)

        self.dictate_button = ctk.CTkButton(
            self,
            text="🎤",
            width=44,
            height=40,
            corner_radius=theme.CORNER_RADIUS,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17),
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.TEXT_MUTED,
            command=self._toggle_dictation,
        )
        self.dictate_button.grid(row=1, column=3, padx=4, pady=10)

        self.send_button = ctk.CTkButton(
            self,
            text="Enviar",
            width=90,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            command=self._handle_send_or_stop,
        )
        self.send_button.grid(row=1, column=4, padx=(4, 12), pady=10)

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

    _RESIZE_DEBOUNCE_MS = 60

    def _on_key_release(self, _event=None) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(self._RESIZE_DEBOUNCE_MS, self._run_debounced_autosize)

    def _run_debounced_autosize(self) -> None:
        self._resize_job = None
        self._autosize_input()

    def _autosize_input(self) -> None:
        if getattr(self, "_showing_placeholder", False):
            self._set_input_height(self._MIN_HEIGHT)
            return

        try:
            display_lines = self.text_entry._textbox.count("1.0", "end", "displaylines")[0]
            line_info = self.text_entry._textbox.dlineinfo("1.0")
            line_height = line_info[3] if line_info else 17
        except Exception:
            return

        chrome_padding = self._MIN_HEIGHT - line_height
        target_height = line_height * max(display_lines, 1) + chrome_padding
        self._set_input_height(max(self._MIN_HEIGHT, min(target_height, self._MAX_HEIGHT)))

    def _set_input_height(self, height: int) -> None:
        if height != self._current_height:
            self._current_height = height
            self.text_entry.configure(height=height)

    def _handle_return(self, event) -> str:
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

        attachment_path = self._pending_attachment_path
        self.text_entry.delete("1.0", "end")
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        self._set_input_height(self._MIN_HEIGHT)
        self.clear_pending_attachment()

        if self._on_send:
            self._on_send(text, attachment_path)

    def _attach_file(self) -> None:
        if self._on_attach:
            self._on_attach()

    def _toggle_dictation(self) -> None:
        if self._on_dictate_toggle:
            self._on_dictate_toggle()

    def _toggle_file_context(self) -> None:
        if self._on_toggle_file_context:
            self._on_toggle_file_context()

    def set_file_context_state(self, active: bool, enabled: bool) -> None:
        """
        Refleja si hay un archivo "fijado" en esta conversación (se
        puede seguir preguntando sobre él sin volver a adjuntarlo).
        `enabled` es False hasta que se envía el primer archivo en la
        conversación — antes de eso el botón queda deshabilitado, como
        el de dictado antes de tener un motor compatible.
        """
        if not enabled:
            self.file_context_button.configure(
                state="disabled", fg_color="transparent", text_color=theme.SIDEBAR_TEXT_DISABLED
            )
            return

        if active:
            self.file_context_button.configure(
                state="normal", fg_color=theme.PRIMARY_RED, text_color="#FFFFFF",
                hover_color=theme.PRIMARY_RED_HOVER,
            )
        else:
            self.file_context_button.configure(
                state="normal", fg_color="transparent", text_color=theme.TEXT_MUTED,
                hover_color=theme.PRIMARY_RED_LIGHT,
            )

    def set_dictating(self, dictating: bool) -> None:
        """
        Llamado por MainWindow para reflejar visualmente si hay una
        grabación en curso — el micrófono real lo maneja
        core/audio_recorder.py, este método solo actualiza el botón.
        """
        self._is_dictating = dictating
        if dictating:
            self.dictate_button.configure(text="⏹", fg_color=theme.STATUS_RED, text_color="#FFFFFF")
        else:
            self.dictate_button.configure(text="🎤", fg_color="transparent", text_color=theme.TEXT_MUTED)

    def insert_dictated_text(self, text: str) -> None:
        """Inserta el texto transcripto en el cuadro, para que el usuario lo revise antes de enviar."""
        if getattr(self, "_showing_placeholder", False):
            self._clear_placeholder()
        current = self.text_entry.get("1.0", "end").strip()
        separator = " " if current else ""
        self.text_entry.insert("end", f"{separator}{text}")
        self._autosize_input()

    def set_pending_attachment(self, file_path: str, display_name: str) -> None:
        self._pending_attachment_path = file_path
        self.attachment_label.configure(text=f"📎 {display_name}")
        self.attachment_chip.grid(row=0, column=0, columnspan=5, padx=12, pady=(8, 0), sticky="w")

    def clear_pending_attachment(self) -> None:
        self._pending_attachment_path = None
        self.attachment_chip.grid_forget()

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
                text="Enviar", fg_color=theme.PRIMARY_RED, hover_color=theme.PRIMARY_RED_HOVER
            )


class ChatPanel(ctk.CTkFrame):

    def __init__(
        self,
        master,
        on_send_message=None,
        on_stop_generation=None,
        on_attach_file=None,
        on_regenerate_message=None,
        on_dictate_toggle=None,
        on_toggle_file_context=None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, **kwargs)
        self._on_send_message = on_send_message
        self._on_stop_generation = on_stop_generation
        self._on_attach_file = on_attach_file
        self._on_regenerate_message = on_regenerate_message
        self._on_dictate_toggle = on_dictate_toggle
        self._on_toggle_file_context = on_toggle_file_context
        self._typing_indicator: TypingIndicator | None = None
        self._has_conversation = False
        self._last_user_text: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.home_greeting = HomeGreeting(self)
        self.home_greeting.grid(row=0, column=0, sticky="nsew")

        self.messages_container = ctk.CTkScrollableFrame(
            self, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0
        )

        self.input_bar = ChatInputBar(
            self,
            on_send=self._handle_user_message,
            on_stop=self._handle_stop_requested,
            on_attach=self._on_attach_file,
            on_dictate_toggle=self._on_dictate_toggle,
            on_toggle_file_context=self._on_toggle_file_context,
        )
        self.input_bar.grid(row=1, column=0, sticky="ew")

    def show_home(self, greeting_text: str) -> None:
        self._has_conversation = False
        self._last_user_text = None
        self.messages_container.grid_forget()
        self.home_greeting.set_greeting(greeting_text)
        self.home_greeting.grid(row=0, column=0, sticky="nsew")

    def start_new_conversation(self) -> None:
        self._has_conversation = True
        self._last_user_text = None
        self.home_greeting.grid_forget()

        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._typing_indicator = None

        self.messages_container.grid(row=0, column=0, sticky="nsew")

    def load_conversation(self, messages: list[Message]) -> None:
        self._has_conversation = True
        self._last_user_text = None
        self.home_greeting.grid_forget()

        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._typing_indicator = None

        self.messages_container.grid(row=0, column=0, sticky="nsew")

        for message in messages:
            self._add_bubble_for_message(message)
        self._scroll_to_bottom()

    def _add_bubble_for_message(self, message: Message) -> MessageBubble:
        on_regenerate = None
        if not message.is_user and self._last_user_text is not None and self._on_regenerate_message:
            question = self._last_user_text
            on_regenerate = lambda q=question: self._on_regenerate_message(q)

        bubble = MessageBubble(self.messages_container, message, on_regenerate=on_regenerate)
        bubble.pack(fill="x", padx=4, pady=2)

        if message.is_user:
            self._last_user_text = message.content

        return bubble

    def add_message(self, message: Message) -> MessageBubble:
        if not self._has_conversation:
            self.start_new_conversation()
        bubble = self._add_bubble_for_message(message)
        self._scroll_to_bottom()
        return bubble

    def show_typing_indicator(self) -> None:
        if not self._has_conversation:
            self.start_new_conversation()
        if self._typing_indicator is None:
            self._typing_indicator = TypingIndicator(self.messages_container)
        self._typing_indicator.pack(anchor="w", padx=12, pady=4)
        self._typing_indicator.start()
        self._scroll_to_bottom()

    def hide_typing_indicator(self) -> None:
        if self._typing_indicator is not None:
            try:
                self._typing_indicator.stop()
                self._typing_indicator.destroy()
            except Exception:
                pass
            self._typing_indicator = None

    def start_streaming_assistant_bubble(self) -> MessageBubble:
        if not self._has_conversation:
            self.start_new_conversation()

        on_regenerate = None
        if self._last_user_text is not None and self._on_regenerate_message:
            question = self._last_user_text
            on_regenerate = lambda q=question: self._on_regenerate_message(q)

        placeholder_message = Message(content="", sender=Sender.ASSISTANT, timestamp=datetime.now().strftime("%H:%M"))
        bubble = MessageBubble(self.messages_container, placeholder_message, on_regenerate=on_regenerate, streaming=True)
        bubble.pack(fill="x", padx=4, pady=2)
        self._scroll_to_bottom()
        return bubble

    def append_to_streaming_bubble(self, bubble: MessageBubble, delta: str) -> None:
        bubble.append_streaming_text(delta)
        self._scroll_to_bottom()

    def finalize_streaming_bubble(self, bubble: MessageBubble, final_message: Message) -> None:
        bubble.finalize(final_message)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        self.messages_container.update_idletasks()
        try:
            self.messages_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def set_generating(self, generating: bool) -> None:
        self.input_bar.set_generating(generating)

    def set_file_context_state(self, active: bool, enabled: bool) -> None:
        self.input_bar.set_file_context_state(active, enabled)

    def _handle_user_message(self, text: str, attachment_path: str | None = None) -> None:
        if self._on_send_message:
            self._on_send_message(text, attachment_path)

    def _handle_stop_requested(self) -> None:
        if self._on_stop_generation:
            self._on_stop_generation()


class HistoryPanel(ctk.CTkScrollableFrame):

    def __init__(self, master, on_select_conversation=None, on_delete_conversation=None, on_export_conversation=None, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._on_select_conversation = on_select_conversation
        self._on_delete_conversation = on_delete_conversation
        self._on_export_conversation = on_export_conversation

    def refresh(self, grouped_conversations) -> None:
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
            time_text = datetime.fromisoformat(conversation.created_at).strftime("%H:%M")
        except ValueError:
            pass

        item_button = ctk.CTkButton(
            row,
            text=f"💬  {conversation.title}",
            anchor="w",
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.TEXT_DARK,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            command=lambda cid=conversation.id: self._handle_select(cid),
        )
        item_button.pack(side="left", fill="x", expand=True)

        delete_button = ctk.CTkButton(
            row,
            text="🗑",
            width=28,
            height=24,
            fg_color="transparent",
            hover_color=theme.STATUS_RED,
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            command=lambda cid=conversation.id, title=conversation.title: self._handle_delete(cid, title),
        )
        delete_button.pack(side="right", padx=(4, 4))

        export_button = ctk.CTkButton(
            row,
            text="📤",
            width=28,
            height=24,
            fg_color="transparent",
            hover_color=theme.PRIMARY_RED_LIGHT,
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            command=lambda cid=conversation.id, title=conversation.title: self._handle_export(cid, title),
        )
        export_button.pack(side="right", padx=(4, 0))

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

    def _handle_export(self, conversation_id: int, title: str) -> None:
        if self._on_export_conversation:
            self._on_export_conversation(conversation_id, title)

    def _handle_delete(self, conversation_id: int, title: str) -> None:
        confirmed = messagebox.askyesno(
            "Eliminar conversación",
            f'¿Eliminar "{title}"?\n\nEsta acción no se puede deshacer.',
            parent=self,
        )
        if confirmed and self._on_delete_conversation:
            self._on_delete_conversation(conversation_id)
