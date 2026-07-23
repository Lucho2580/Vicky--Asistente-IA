"""
Panel de estado inferior.

Muestra tres indicadores: estado de la IA, estado de la base de datos
y usuario conectado. Los dos primeros se muestran como "chips" (punto
+ texto, con fondo pastel del color correspondiente) en vez de un
punto de color suelto — se lee más rápido de un vistazo. Cada uno se
puede actualizar dinámicamente desde el código (por ejemplo, cuando se
conecte un motor de IA real o una base de datos SQL Server).
"""
import customtkinter as ctk

from ui import theme


class StatusChip(ctk.CTkFrame):
    """Píldora de estado: punto de color + texto, con fondo pastel a tono."""

    def __init__(self, master, label: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        label_widget = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        label_widget.pack(side="left", padx=(0, 6))

        self._pill = ctk.CTkFrame(self, fg_color=theme.STATUS_NEUTRAL_BG, corner_radius=10, height=22)
        self._pill.pack(side="left")
        self._pill.pack_propagate(False)

        pill_content = ctk.CTkFrame(self._pill, fg_color="transparent")
        pill_content.place(relx=0.5, rely=0.5, anchor="center")

        self._dot = ctk.CTkLabel(
            pill_content, text="●", font=ctk.CTkFont(size=8), text_color=theme.STATUS_NEUTRAL_TEXT,
        )
        self._dot.pack(side="left", padx=(10, 5))

        self._text = ctk.CTkLabel(
            pill_content, text="Desconectado",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL - 1, weight="bold"),
            text_color=theme.STATUS_NEUTRAL_TEXT,
        )
        self._text.pack(side="left", padx=(0, 10))

    def set_state(self, connected: bool, text: str) -> None:
        bg = theme.STATUS_GREEN_BG if connected else theme.STATUS_NEUTRAL_BG
        fg = theme.STATUS_GREEN_TEXT if connected else theme.STATUS_NEUTRAL_TEXT
        self._pill.configure(fg_color=bg)
        self._dot.configure(text_color=fg)
        self._text.configure(text=text, text_color=fg)


class StatusBar(ctk.CTkFrame):
    """Barra inferior con el estado de IA, base de datos y usuario."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=0,
            height=38,
            **kwargs,
        )
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_propagate(False)
        self.grid_columnconfigure(2, weight=1)

        self.ai_status = StatusChip(self, "IA:")
        self.ai_status.grid(row=0, column=0, padx=(20, 20), pady=8, sticky="w")

        self.db_status = StatusChip(self, "Base de datos:")
        self.db_status.grid(row=0, column=1, padx=(0, 20), pady=8, sticky="w")

        self.user_status = ctk.CTkLabel(
            self, text="Usuario: Invitado",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        self.user_status.grid(row=0, column=3, padx=20, pady=8, sticky="e")

    # ------------------------------------------------------------------ #
    # API pública para actualizar el estado desde el resto de la app
    # ------------------------------------------------------------------ #
    def set_ai_status(self, connected: bool, engine_name: str = "") -> None:
        text = f"Conectada · {engine_name}" if connected and engine_name else ("Conectada" if connected else "Desconectado")
        self.ai_status.set_state(connected, text)

    def set_db_status(self, connected: bool, engine_name: str = "SQL Server") -> None:
        text = engine_name if connected else "Desconectado"
        self.db_status.set_state(connected, text)

    def set_user(self, username: str) -> None:
        self.user_status.configure(text=f"Usuario: {username or 'Invitado'}")
