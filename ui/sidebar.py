"""
Menú lateral de navegación.

Botones habilitados (con acción real de navegación):
    Inicio, Nuevo Chat, Historial, Configuración

Botones deshabilitados (funcionalidad futura):
    Tickets, Ayuda, Acerca de
    -> se muestran en gris, con el texto "(Próximamente)" y no
       responden al clic.

El botón correspondiente a la vista actualmente seleccionada se
resalta con el color de acento azul.
"""
import customtkinter as ctk

from ui import theme


class SidebarButton(ctk.CTkButton):
    """Botón de navegación individual con estado seleccionable."""

    def __init__(self, master, text: str, command=None, enabled: bool = True, **kwargs):
        self._enabled = enabled
        display_text = text if enabled else f"{text}  (Próximamente)"

        super().__init__(
            master,
            text=display_text,
            command=command if enabled else None,
            anchor="w",
            corner_radius=theme.CORNER_RADIUS,
            fg_color="transparent",
            hover_color=theme.SIDEBAR_BG_HOVER if enabled else theme.SIDEBAR_BG,
            text_color=theme.SIDEBAR_TEXT if enabled else theme.SIDEBAR_TEXT_DISABLED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            height=40,
            state="normal" if enabled else "disabled",
            **kwargs,
        )

    def set_selected(self, selected: bool) -> None:
        """Resalta (o quita el resalte) este botón como opción activa."""
        if not self._enabled:
            return
        if selected:
            self.configure(fg_color=theme.SIDEBAR_SELECTED, text_color="#FFFFFF")
        else:
            self.configure(fg_color="transparent", text_color=theme.SIDEBAR_TEXT)


class Sidebar(ctk.CTkFrame):
    """Panel lateral con las secciones de navegación de la aplicación."""

    def __init__(self, master, on_navigate=None, **kwargs):
        super().__init__(master, fg_color=theme.SIDEBAR_BG, corner_radius=0, **kwargs)
        self._on_navigate = on_navigate
        self._buttons: dict[str, SidebarButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            self,
            text="La Vianda",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_TITLE, weight="bold"),
            text_color="#FFFFFF",
        )
        header.grid(row=0, column=0, padx=16, pady=(20, 16), sticky="w")

        entries = [
            ("home", "🏠  Inicio", True),
            ("new_chat", "💬  Nuevo Chat", True),
            ("history", "🕒  Historial", True),
            ("tickets", "🎫  Tickets", False),
            ("settings", "⚙  Configuración", True),
            ("help", "❓  Ayuda", False),
            ("about", "ℹ  Acerca de", False),
        ]

        row = 1
        for key, label, enabled in entries:
            button = SidebarButton(
                self,
                text=label,
                enabled=enabled,
                command=(lambda k=key: self._handle_click(k)) if enabled else None,
            )
            button.grid(row=row, column=0, padx=10, pady=3, sticky="ew")
            self._buttons[key] = button
            row += 1

        # Empuja el contenido hacia arriba dejando espacio libre abajo.
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.grid(row=row, column=0, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)

    def _handle_click(self, key: str) -> None:
        self.select(key)
        if self._on_navigate:
            self._on_navigate(key)

    def select(self, key: str) -> None:
        """Marca visualmente `key` como la sección activa."""
        for name, button in self._buttons.items():
            button.set_selected(name == key)
