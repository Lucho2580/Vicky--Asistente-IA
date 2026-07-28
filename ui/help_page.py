import customtkinter as ctk

from config.app_config import AppConfig
from core.version import APP_BUILD, APP_VERSION
from ui import theme
from ui.settings_window import Card


class CollapsibleHelpCard(ctk.CTkFrame):

    def __init__(self, master, title: str, bullet_points: list[str], expanded: bool = False, **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            **kwargs,
        )
        self.title = title
        self.bullet_points = bullet_points
        self.search_haystack = (title + " " + " ".join(bullet_points)).lower()
        self._expanded = expanded
        self._build_ui()

    def _build_ui(self) -> None:
        self.header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.header.pack(fill="x")
        self.header.bind("<Button-1>", self._toggle)

        self.title_label = ctk.CTkLabel(
            self.header,
            text=self.title,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
            cursor="hand2",
        )
        self.title_label.pack(side="left", padx=20, pady=14)
        self.title_label.bind("<Button-1>", self._toggle)

        self.chevron_label = ctk.CTkLabel(
            self.header,
            text="▾" if self._expanded else "▸",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            cursor="hand2",
        )
        self.chevron_label.pack(side="right", padx=20)
        self.chevron_label.bind("<Button-1>", self._toggle)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        for point in self.bullet_points:
            label = ctk.CTkLabel(
                self.body,
                text=f"•  {point}",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
                text_color=theme.TEXT_DARK,
                wraplength=560,
                justify="left",
                anchor="w",
            )
            label.pack(anchor="w", padx=20, pady=3, fill="x")
        ctk.CTkFrame(self.body, fg_color="transparent", height=10).pack()

        if self._expanded:
            self.body.pack(fill="x")

    def _toggle(self, _event=None) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="x")
            self.chevron_label.configure(text="▾")
        else:
            self.body.pack_forget()
            self.chevron_label.configure(text="▸")

    def matches(self, query: str) -> bool:
        return query in self.search_haystack


class HelpPage(ctk.CTkScrollableFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._config = AppConfig()
        self._cards: list[CollapsibleHelpCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Ayuda",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title.pack(anchor="w", padx=24, pady=(20, 2))

        subtitle = ctk.CTkLabel(
            self,
            text="Guía rápida para sacarle el máximo provecho a Vicky.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 12))

        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text='Buscar en la ayuda... (ej. "adjuntar imagen")',
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.SURFACE_WHITE,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
        )
        self.search_entry.pack(fill="x", padx=24, pady=(0, 14))
        self.search_entry.bind("<KeyRelease>", self._handle_search)

        self._build_novedades_card()

        engine_name = self._config.settings.ai_engine or "sin configurar"

        self._add_card(
            "💬 Cómo escribir",
            [
                "Escribí tu pregunta en el cuadro de abajo y presioná Enter para enviarla.",
                "Usá Shift + Enter si querés escribir varias líneas antes de enviar — el cuadro va creciendo solo con lo que escribís.",
                'Mientras la IA está respondiendo, el botón "Enviar" cambia a "Detener" — podés cortar la respuesta en cualquier momento sin perder lo que ya llegó.',
                "Vicky recuerda los últimos mensajes de la conversación activa, así que podés hacer preguntas de seguimiento sin repetir el contexto.",
            ],
            expanded=True,
        )

        self._add_card(
            "📎 Adjuntar archivos e imágenes",
            [
                "Podés adjuntar documentos (.txt, .md, .csv, .json, .log, .pdf, .docx) o imágenes (.png, .jpg, .webp, .gif) desde el botón 📎 del chat.",
                "El archivo queda pendiente (se ve como una etiqueta arriba del cuadro de texto) hasta que presionás Enviar — recién ahí se usa.",
                "Se usa solo para responder esa pregunta puntual: no se guarda en la Base de Conocimiento ni queda disponible después.",
                'Con imágenes podés preguntar cosas como "¿qué error es este?" adjuntando una captura de pantalla.',
            ],
        )

        self._add_card(
            "🎤 Chat de voz",
            [
                "Tocá el botón 🎤 para empezar a grabar tu pregunta por micrófono, y tocalo de nuevo para terminar.",
                "El texto transcripto aparece en el cuadro para que lo revises (y corrijas si hace falta) antes de enviarlo — no se manda solo.",
                "Si el motor de IA actual no soporta transcripción de voz, te avisa y podés escribir tu pregunta normalmente.",
            ],
        )

        self._add_card(
            "🕒 Historial",
            [
                "Todas tus conversaciones se guardan automáticamente, agrupadas por Hoy / Ayer / Últimos 7 días / Este mes / Más antiguas.",
                "Hacé clic en cualquier conversación para retomarla exactamente donde quedó, con todos sus mensajes.",
                "Usá el ícono 🗑 junto a cada conversación para eliminarla de forma permanente (te va a pedir confirmación antes de borrar).",
            ],
        )

        self._add_card(
            "✨ En cada respuesta de la IA",
            [
                '"Copiar" copia el texto completo de la respuesta al portapapeles.',
                '"↻ Regenerar" vuelve a pedir una respuesta para la misma pregunta anterior, por si la primera no te sirvió (se agrega debajo, sin borrar la anterior).',
            ],
        )

        self._add_card(
            "🔑 Motor de IA",
            [
                f"El asistente está usando {engine_name} y se conecta automáticamente al iniciar la app.",
                "El estado de conexión se ve arriba a la derecha del encabezado (🟢 conectado / 🟡 conectando / 🔴 sin conexión).",
                "Se puede cambiar de motor desde Configuración, si tenés permisos de administrador.",
            ],
        )

        self._build_support_card()

        self._no_results_label = ctk.CTkLabel(
            self,
            text="No encontramos nada con esa búsqueda.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )

    def _build_novedades_card(self) -> None:
        card = ctk.CTkFrame(
            self, fg_color=theme.PRIMARY_RED_LIGHT, corner_radius=theme.CORNER_RADIUS,
            border_width=1, border_color="#F3C7C9",
        )
        card.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            card,
            text=f"🆕 Novedades de la versión {APP_VERSION} (build {APP_BUILD})",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color="#8A1418",
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            card,
            text=(
                "Memoria de conversación, adjuntar imágenes, soporte de PDF y Word en la Base "
                "de Conocimiento, búsqueda semántica, y chat de voz por micrófono."
            ),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color="#8A1418",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _build_support_card(self) -> None:
        card = Card(self, "¿No encontraste lo que buscabas?")
        card.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(
            card,
            text="Escribile al administrador del sistema de tu empresa para pedir ayuda o sugerir una mejora.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_DARK,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 4))
        card.add_footer_spacer()

    def _add_card(self, title: str, bullet_points: list[str], expanded: bool = False) -> None:
        card = CollapsibleHelpCard(self, title, bullet_points, expanded=expanded)
        card.pack(fill="x", padx=24, pady=6)
        self._cards.append(card)

    def _handle_search(self, _event=None) -> None:
        query = self.search_entry.get().strip().lower()

        if not query:
            for card in self._cards:
                card.pack(fill="x", padx=24, pady=6)
            self._no_results_label.pack_forget()
            return

        any_visible = False
        for card in self._cards:
            if card.matches(query):
                card.pack(fill="x", padx=24, pady=6)
                any_visible = True
            else:
                card.pack_forget()

        if any_visible:
            self._no_results_label.pack_forget()
        else:
            self._no_results_label.pack(anchor="w", padx=24, pady=20)
