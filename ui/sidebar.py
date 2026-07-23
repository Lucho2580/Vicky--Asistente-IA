"""
Menú lateral de navegación.

Botones habilitados (con acción real de navegación), agrupados en dos
secciones:
    PRINCIPAL: Inicio, Nuevo Chat, Historial
    SISTEMA:   Tickets (deshabilitado), Configuración, Ayuda, Acerca de

El botón correspondiente a la vista actualmente seleccionada se
resalta con el color de acento rojo (corporativo de La Vianda). Al
pie, separado por una línea, se muestra el usuario logueado (avatar
con iniciales + nombre) — si inició sesión con Microsoft, es su
nombre real.
"""
import customtkinter as ctk
from PIL import Image

from ui import theme
from ui.assets_path import get_asset_path

_LOGO_PATH = get_asset_path("logo.png")


def _initials_from_name(name: str) -> str:
    """'Luis Enrique' -> 'LE'. Un solo nombre -> su primera letra."""
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[1][0]).upper()


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
            height=38,
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

    def __init__(self, master, on_navigate=None, display_name: str | None = None, **kwargs):
        super().__init__(master, fg_color=theme.SIDEBAR_BG, corner_radius=0, **kwargs)
        self._on_navigate = on_navigate
        self._display_name = display_name
        self._buttons: dict[str, SidebarButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # --- Encabezado: logo + nombre de la app ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(20, 18), sticky="w")

        try:
            logo_image = ctk.CTkImage(Image.open(_LOGO_PATH), size=(24, 24))
            ctk.CTkLabel(header, image=logo_image, text="").pack(side="left", padx=(0, 8))
        except Exception:
            pass  # si el logo no está disponible, se sigue sin él

        ctk.CTkLabel(
            header,
            text="Vicky Consulting",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_TITLE, weight="bold"),
            text_color="#FFFFFF",
        ).pack(side="left")

        row = self._add_section(1, "PRINCIPAL", [
            ("home", "🏠  Inicio", True),
            ("new_chat", "💬  Nuevo Chat", True),
            ("history", "🕒  Historial", True),
        ])
        row = self._add_section(row, "SISTEMA", [
            ("tickets", "🎫  Tickets", False),
            ("settings", "⚙  Configuración", True),
            ("help", "❓  Ayuda", True),
            ("about", "ℹ  Acerca de", True),
        ])

        # Empuja el pie de usuario hacia abajo, dejando el espacio
        # sobrante en el medio (no al fondo, como quedaba antes).
        self.grid_rowconfigure(row, weight=1)
        row += 1

        self._build_user_footer(row)

    def _add_section(self, start_row: int, label: str, entries: list[tuple[str, str, bool]]) -> int:
        row = start_row
        section_label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9, weight="bold"),
            text_color=theme.SIDEBAR_TEXT_DISABLED,
        )
        section_label.grid(row=row, column=0, padx=20, pady=(6, 4), sticky="w")
        row += 1

        for key, text, enabled in entries:
            button = SidebarButton(
                self,
                text=text,
                enabled=enabled,
                command=(lambda k=key: self._handle_click(k)) if enabled else None,
            )
            button.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
            self._buttons[key] = button
            row += 1

        return row

    def _build_user_footer(self, row: int) -> None:
        name = self._display_name or "Sin identificar"

        footer = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        footer.grid(row=row, column=0, sticky="ew")

        separator = ctk.CTkFrame(footer, fg_color=theme.SIDEBAR_BG_HOVER, height=1)
        separator.pack(fill="x", padx=16, pady=(0, 10))

        content = ctk.CTkFrame(footer, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=(0, 16))

        avatar = ctk.CTkFrame(content, width=30, height=30, corner_radius=15, fg_color=theme.PRIMARY_RED)
        avatar.pack(side="left", padx=(0, 10))
        avatar.pack_propagate(False)
        ctk.CTkLabel(
            avatar, text=_initials_from_name(name),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold"), text_color="#FFFFFF",
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            content, text=name,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
            text_color="#FFFFFF", anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _handle_click(self, key: str) -> None:
        self.select(key)
        if self._on_navigate:
            self._on_navigate(key)

    def select(self, key: str) -> None:
        """Marca visualmente `key` como la sección activa."""
        for name, button in self._buttons.items():
            button.set_selected(name == key)
