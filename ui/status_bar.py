"""
Panel de estado inferior.

Muestra tres indicadores: estado de la IA, estado de la base de datos
y usuario conectado. Cada uno se puede actualizar dinámicamente desde
el código (por ejemplo, cuando se conecte un motor de IA real o una
base de datos SQL Server).
"""
import customtkinter as ctk

from ui import theme


class StatusItem(ctk.CTkFrame):
    """Un par etiqueta/valor dentro de la barra de estado (ej. 'IA: 🟢 Conectada')."""

    def __init__(self, master, label: str, value: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        label_widget = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        label_widget.pack(side="left", padx=(0, 4))

        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        self.value_label.pack(side="left")

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value)


class StatusBar(ctk.CTkFrame):
    """Barra inferior con el estado de IA, base de datos y usuario."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=0,
            height=32,
            **kwargs,
        )
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_propagate(False)
        self.grid_columnconfigure(3, weight=1)

        self.ai_status = StatusItem(self, "IA:", "🔴 Desconectado")
        self.ai_status.grid(row=0, column=0, padx=16, pady=4, sticky="w")

        self.db_status = StatusItem(self, "Base de datos:", "🔴 Desconectado")
        self.db_status.grid(row=0, column=1, padx=16, pady=4, sticky="w")

        self.user_status = StatusItem(self, "Usuario:", "Invitado")
        self.user_status.grid(row=0, column=2, padx=16, pady=4, sticky="w")

    # ------------------------------------------------------------------ #
    # API pública para actualizar el estado desde el resto de la app
    # ------------------------------------------------------------------ #
    def set_ai_status(self, connected: bool, engine_name: str = "") -> None:
        if connected:
            self.ai_status.set_value(f"🟢 Conectada ({engine_name})" if engine_name else "🟢 Conectada")
        else:
            self.ai_status.set_value("🔴 Desconectado")

    def set_db_status(self, connected: bool, engine_name: str = "SQL Server") -> None:
        if connected:
            self.db_status.set_value(f"🟢 {engine_name}")
        else:
            self.db_status.set_value("🔴 Desconectado")

    def set_user(self, username: str) -> None:
        self.user_status.set_value(username or "Invitado")
