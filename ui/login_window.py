"""
Pantalla de login, mostrada como un OVERLAY dentro de la misma ventana
raíz de la aplicación — no como una segunda ventana/raíz de Tkinter
separada.

Esto es importante y corrige un bug real: customtkinter mantiene un
rastreador interno de escala de pantalla (DPI) por cada raíz `ctk.CTk()`
que se crea. Si se crea una raíz para el login y, al terminar, se la
destruye para crear una raíz DISTINTA para la ventana principal, ese
rastreador deja llamadas `after()` programadas contra un intérprete
Tcl que ya no existe — y aparecen errores como:

    invalid command name "...update"
    invalid command name "..._set_scaled_min_max"
    invalid command name "...check_dpi_scaling"

La solución es tener una única raíz `ctk.CTk()` para toda la vida de
la aplicación (ver ui/main_window.py): el login es solo un `CTkFrame`
que se muestra primero y se destruye a sí mismo al terminar, dejando
lugar al resto de la interfaz en la MISMA ventana.

Diseño: tarjeta centrada de panel dividido — el panel izquierdo (gris
oscuro, con el logo real de La Vianda) queda fijo durante todo el
proceso; el panel derecho cambia de contenido según el paso (botón de
login -> código de dispositivo), sin que la tarjeta cambie de tamaño
ni de posición entre un paso y el otro.

Intenta primero un login silencioso (si ya se inició sesión antes en
esta computadora, no vuelve a pedir nada). Si no hay sesión guardada,
exige "Iniciar sesión con Microsoft" (código de dispositivo) — el
acceso está centralizado en la cuenta de correo de Microsoft, no
existe una vía para entrar sin loguearse.
"""
import os
import sys
import threading
import webbrowser

import customtkinter as ctk
from PIL import Image

from core.microsoft_auth import MicrosoftAuthService, is_configured
from ui import theme

if getattr(sys, "frozen", False):
    # Compilado con PyInstaller: los assets NO quedan necesariamente
    # junto al .exe — desde PyInstaller 6, en modo "one-folder" van
    # adentro de una subcarpeta "_internal". `sys._MEIPASS` es la forma
    # correcta y estable (funciona igual en onefile y one-folder, en
    # cualquier versión) de encontrar dónde quedaron los datos
    # empaquetados — ver packaging/pyinstaller/app.spec, que copia
    # ui/assets ahí mismo.
    _BASE_DIR = sys._MEIPASS
else:
    # Corriendo desde código fuente: __file__ sí apunta a la ruta real.
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_LOGO_PATH = os.path.join(_BASE_DIR, "ui", "assets", "logo.png")

CARD_WIDTH = 640
CARD_HEIGHT = 420
LEFT_PANEL_WIDTH = 240


class LoginOverlay(ctk.CTkFrame):
    """Overlay de login, mostrado dentro de la ventana principal antes que el resto de la UI."""

    def __init__(self, master, on_complete, **kwargs):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)

        self._on_complete = on_complete
        self._auth_service = MicrosoftAuthService()
        self._completed = False

        self._build_ui()
        # Intenta continuar la sesión anterior sin pedirle nada al usuario.
        self.after(200, self._try_silent_login)

    def _build_ui(self) -> None:
        # Tarjeta centrada (panel dividido), flotando sobre el fondo neutro.
        card = ctk.CTkFrame(
            self,
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------------------ #
        # Panel izquierdo: fijo, gris oscuro corporativo, logo real.
        # No cambia entre el paso del botón y el paso del código.
        # ------------------------------------------------------------ #
        left_panel = ctk.CTkFrame(
            card, width=LEFT_PANEL_WIDTH, fg_color=theme.SIDEBAR_BG, corner_radius=0
        )
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.grid_propagate(False)

        logo_container = ctk.CTkFrame(left_panel, fg_color="transparent")
        logo_container.place(relx=0.5, rely=0.5, anchor="center")

        try:
            logo_image = ctk.CTkImage(Image.open(_LOGO_PATH), size=(72, 72))
            logo_label = ctk.CTkLabel(logo_container, image=logo_image, text="")
            logo_label.pack(pady=(0, 14))
        except Exception:
            pass  # si el archivo del logo no está disponible, se sigue sin él

        brand_label = ctk.CTkLabel(
            logo_container,
            text="Vicky\nConsulting",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=17, weight="bold"),
            text_color="#FFFFFF",
            justify="center",
        )
        brand_label.pack()

        # ------------------------------------------------------------ #
        # Panel derecho: cambia de contenido según el paso (botón <-> código).
        # ------------------------------------------------------------ #
        self._right_panel = ctk.CTkFrame(card, fg_color="transparent")
        self._right_panel.grid(row=0, column=1, sticky="nsew", padx=36, pady=32)

        right_content = ctk.CTkFrame(self._right_panel, fg_color="transparent")
        right_content.place(relx=0.5, rely=0.5, anchor="center")

        title = ctk.CTkLabel(
            right_content,
            text="Bienvenido de nuevo",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title.pack(pady=(0, 4))

        subtitle = ctk.CTkLabel(
            right_content,
            text="Iniciá sesión con tu cuenta corporativa para continuar.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
            wraplength=320,
            justify="center",
        )
        subtitle.pack(pady=(0, 22))

        self._login_button = ctk.CTkButton(
            right_content,
            text="🔑 Iniciar sesión con Microsoft",
            width=300,
            height=42,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            command=self._handle_login_click,
        )
        self._login_button.pack(pady=(0, 12))

        if not is_configured():
            self._login_button.configure(state="disabled")

        # --- Área del código de dispositivo (oculta hasta que haga falta) ---
        self._code_frame = ctk.CTkFrame(right_content, fg_color="transparent")

        code_instructions = ctk.CTkLabel(
            self._code_frame,
            text="Andá a",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        code_instructions.pack(pady=(0, 2))

        self._url_label = ctk.CTkLabel(
            self._code_frame,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.PRIMARY_RED,
        )
        self._url_label.pack(pady=(0, 14))

        code_box = ctk.CTkFrame(self._code_frame, fg_color=theme.BACKGROUND_LIGHT, corner_radius=theme.CORNER_RADIUS)
        code_box.pack(fill="x", pady=(0, 10))

        self._code_label = ctk.CTkLabel(
            code_box,
            text="",
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        self._code_label.pack(padx=16, pady=12)

        copy_code_button = ctk.CTkButton(
            self._code_frame,
            text="Copiar código",
            width=300,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            text_color=theme.TEXT_DARK,
            hover_color=theme.BACKGROUND_LIGHT,
            command=self._copy_code,
        )
        copy_code_button.pack(pady=(0, 12))

        waiting_row = ctk.CTkFrame(self._code_frame, fg_color="transparent")
        waiting_row.pack()
        dot = ctk.CTkLabel(
            waiting_row, text="●", font=ctk.CTkFont(size=8), text_color=theme.PRIMARY_RED
        )
        dot.pack(side="left", padx=(0, 6))
        waiting_label = ctk.CTkLabel(
            waiting_row,
            text="Esperando confirmación...",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        waiting_label.pack(side="left")

        self._status_label = ctk.CTkLabel(
            right_content,
            text="Verificando si ya iniciaste sesión antes..." if is_configured() else
            "⚠️ El login con Microsoft todavía no está configurado (falta el Client ID). "
            "Contacta al administrador del sistema para poder ingresar.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            wraplength=320,
            justify="center",
        )
        self._status_label.pack(pady=(12, 0))

    # ------------------------------------------------------------------ #
    # Login silencioso (sesión de una vez anterior, si existe)
    # ------------------------------------------------------------------ #
    def _try_silent_login(self) -> None:
        if not is_configured():
            return

        def worker() -> None:
            token_result = self._auth_service.try_silent_login()
            display_name = self._auth_service.get_display_name(token_result) if token_result else None
            self.after(0, lambda: self._handle_silent_result(display_name))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_silent_result(self, display_name: str | None) -> None:
        if display_name:
            self._complete(display_name)
            return
        try:
            self._status_label.configure(text="Inicia sesión con tu cuenta de Microsoft para continuar.")
        except Exception:
            pass  # el overlay ya se pudo haber destruido (login completado por otra vía)

    # ------------------------------------------------------------------ #
    # Login interactivo (código de dispositivo)
    # ------------------------------------------------------------------ #
    def _handle_login_click(self) -> None:
        self._login_button.configure(state="disabled", text="Conectando...")
        self._status_label.configure(text="Conectando con Microsoft...")

        def on_code_ready(code: str, url: str) -> None:
            self.after(0, lambda: self._show_device_code(code, url))

        def worker() -> None:
            success, token_result, message = self._auth_service.login_with_device_code(on_code_ready)
            display_name = None
            if success and token_result:
                display_name = self._auth_service.get_display_name(token_result)
            self.after(0, lambda: self._handle_login_result(success, display_name, message))

        threading.Thread(target=worker, daemon=True).start()

    def _show_device_code(self, code: str, url: str) -> None:
        self._login_button.pack_forget()
        self._code_label.configure(text=code)
        self._url_label.configure(text=url)
        self._code_frame.pack(pady=(0, 12))
        self._status_label.configure(text="")
        try:
            webbrowser.open(url)
        except Exception:
            pass  # sin navegador disponible (ej. entorno headless): el usuario lo abre a mano

    def _handle_login_result(self, success: bool, display_name: str | None, message: str) -> None:
        try:
            self._login_button.configure(state="normal", text="🔑 Iniciar sesión con Microsoft")
        except Exception:
            return  # el overlay ya se pudo haber destruido (login exitoso concurrente)
        if success:
            self._complete(display_name or "Usuario")
        else:
            self._code_frame.pack_forget()
            self._login_button.pack(pady=(0, 12))
            self._status_label.configure(text=f"⚠️ {message}")

    def _copy_code(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self._code_label.cget("text"))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    def _complete(self, display_name: str | None) -> None:
        if self._completed:
            return
        self._completed = True
        try:
            self.destroy()  # destruye este FRAME, nunca la ventana raíz
        except Exception:
            pass
        self._on_complete(display_name)
