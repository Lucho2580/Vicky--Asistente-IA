import customtkinter as ctk

from config.app_config import AppConfig
from ui import theme


class Card(ctk.CTkFrame):

    def __init__(self, master, title: str, description: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            **kwargs,
        )
        self._build_header(title, description)

    def _build_header(self, title: str, description: str) -> None:
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(anchor="w", padx=20, pady=(16, 2))

        if description:
            desc_label = ctk.CTkLabel(
                self,
                text=description,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_MUTED,
            )
            desc_label.pack(anchor="w", padx=20, pady=(0, 10))

    def add_field(self, label_text: str, widget_cls, **widget_kwargs):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)

        label = ctk.CTkLabel(
            row,
            text=label_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            width=170,
            anchor="w",
        )
        label.pack(side="left")

        if widget_cls is ctk.CTkOptionMenu:
            widget_kwargs.setdefault("fg_color", theme.PRIMARY_RED)
            widget_kwargs.setdefault("button_color", theme.PRIMARY_RED_HOVER)
            widget_kwargs.setdefault("button_hover_color", theme.PRIMARY_RED)
            widget_kwargs.setdefault("dropdown_fg_color", theme.SURFACE_WHITE)
            widget_kwargs.setdefault("dropdown_text_color", theme.TEXT_DARK)
            widget_kwargs.setdefault("dropdown_hover_color", theme.BACKGROUND_LIGHT)

        widget = widget_cls(row, **widget_kwargs)
        widget.pack(side="left")
        return widget

    def add_footer_spacer(self) -> None:
        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()


class SettingsPage(ctk.CTkScrollableFrame):

    _SCALE_OPTIONS = ["90%", "100%", "110%", "125%"]

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._config = AppConfig()
        self._build_ui()

    def _build_ui(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Configuración",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title.pack(anchor="w", padx=24, pady=(20, 2))

        subtitle = ctk.CTkLabel(
            self,
            text="Preferencias de esta computadora.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 16))

        self._build_appearance_card()
        self._build_updates_card()

    def _build_appearance_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "APARIENCIA")
        card.pack(fill="x", padx=24, pady=12)

        self.theme_switch = card.add_field(
            "Tema",
            ctk.CTkSegmentedButton,
            values=["Claro", "Oscuro"],
            command=self._handle_theme_change,
            selected_color=theme.PRIMARY_RED,
            selected_hover_color=theme.PRIMARY_RED_HOVER,
        )
        self.theme_switch.set("Oscuro" if settings.theme == "dark" else "Claro")

        scale_value = settings.ui_scale if settings.ui_scale in self._SCALE_OPTIONS else "100%"
        self.scale_menu = card.add_field(
            "Escala de la interfaz",
            ctk.CTkOptionMenu,
            values=self._SCALE_OPTIONS,
            command=self._handle_scale_change,
            width=110,
        )
        self.scale_menu.set(scale_value)

        card.add_footer_spacer()

    def _handle_theme_change(self, value: str) -> None:
        theme_value = "dark" if value == "Oscuro" else "light"
        ctk.set_appearance_mode(theme_value)
        self._config.update(theme=theme_value)

    def _handle_scale_change(self, value: str) -> None:
        try:
            factor = int(value.rstrip("%")) / 100
        except ValueError:
            factor = 1.0
        ctk.set_widget_scaling(factor)
        self._config.update(ui_scale=value)

    def _build_updates_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "ACTUALIZACIONES")
        card.pack(fill="x", padx=24, pady=12)

        self.auto_check_var = ctk.BooleanVar(value=settings.check_updates_on_startup)
        auto_check_switch = ctk.CTkSwitch(
            card,
            text="Buscar actualizaciones automáticamente al iniciar",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            variable=self.auto_check_var,
            onvalue=True,
            offvalue=False,
            command=self._handle_auto_check_toggle,
            progress_color=theme.PRIMARY_RED,
        )
        auto_check_switch.pack(anchor="w", padx=20, pady=(4, 10))

        self.silent_var = ctk.BooleanVar(value=settings.silent_updates_enabled)
        silent_switch = ctk.CTkSwitch(
            card,
            text="Instalar automáticamente sin preguntar",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            variable=self.silent_var,
            onvalue=True,
            offvalue=False,
            command=self._handle_silent_toggle,
            progress_color=theme.PRIMARY_RED,
        )
        silent_switch.pack(anchor="w", padx=20, pady=(0, 4))

        note = ctk.CTkLabel(
            card,
            text=(
                "Si está desactivado, se te va a avisar cuando haya una actualización disponible "
                "y vas a poder decidir cuándo instalarla."
            ),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            wraplength=520,
            justify="left",
        )
        note.pack(anchor="w", padx=20, pady=(0, 12))

        card.add_footer_spacer()

    def _handle_auto_check_toggle(self) -> None:
        self._config.update(check_updates_on_startup=self.auto_check_var.get())

    def _handle_silent_toggle(self) -> None:
        self._config.update(silent_updates_enabled=self.silent_var.get())

    def save(self) -> None:
        pass
