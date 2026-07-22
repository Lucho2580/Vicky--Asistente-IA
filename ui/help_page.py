"""
Página de Ayuda: guía rápida de uso del Asistente IA - La Vianda.

Se muestra dentro del panel principal (igual que Configuración), no en
una ventana aparte.
"""
import customtkinter as ctk

from ui import theme
from ui.settings_window import Card


class HelpPage(ctk.CTkScrollableFrame):
    """Guía rápida de uso, organizada en tarjetas por tema."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
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
            text="Guía rápida para sacarle el máximo provecho al asistente.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 16))

        self._add_card(
            "💬 Cómo escribir",
            [
                "Escribí tu pregunta en el cuadro de abajo y presioná Enter para enviarla.",
                "Usá Shift + Enter si querés escribir varias líneas antes de enviar.",
                'Mientras la IA está respondiendo, el botón "Enviar" cambia a "Detener" — podés cortar la respuesta en cualquier momento sin perder lo que ya llegó.',
            ],
        )

        self._add_card(
            "📎 Archivos de entrenamiento",
            [
                'Podés adjuntar archivos (.txt, .md, .csv, .json, .log) desde el botón 📎 del chat, o colocarlos directamente en la carpeta "Training" (ver Configuración → Base de Conocimiento) sin tener que subirlos uno por uno.',
                "El asistente busca automáticamente en esos archivos antes de responder, y usa su contenido como contexto real para la respuesta.",
                'Si tu pregunta podría aplicar a más de un archivo (ej. "cambiar mi contraseña" cuando hay un procedimiento para el correo y otro para Zeus), el asistente te va a preguntar primero a cuál te referís, en vez de adivinar.',
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
                "El asistente usa GitHub Copilot y se conecta automáticamente al iniciar la app — no hace falta ninguna configuración manual.",
                "El estado de conexión se ve arriba a la derecha del encabezado (🟢 conectado / 🟡 conectando / 🔴 sin conexión).",
            ],
        )

    def _add_card(self, title: str, bullet_points: list[str]) -> None:
        card = Card(self, title)
        card.pack(fill="x", padx=24, pady=8)
        for point in bullet_points:
            label = ctk.CTkLabel(
                card,
                text=f"•  {point}",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
                text_color=theme.TEXT_DARK,
                wraplength=560,
                justify="left",
                anchor="w",
            )
            label.pack(anchor="w", padx=20, pady=3, fill="x")
        card.add_footer_spacer()
