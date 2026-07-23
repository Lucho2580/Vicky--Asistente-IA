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

Intenta primero un login silencioso (si ya se inició sesión antes en
esta computadora, no vuelve a pedir nada). Si no hay sesión guardada,
exige "Iniciar sesión con Microsoft" (código de dispositivo) — el
acceso está centralizado en la cuenta de correo de Microsoft, no
existe una vía para entrar sin loguearse.
"""
import threading
import webbrowser

import customtkinter as ctk

from core.microsoft_auth import MicrosoftAuthService, is_configured
from ui import theme


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
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")

        title = ctk.CTkLabel(
            container,
            text="Asistente IA - La Vianda",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title.pack(pady=(0, 4))

        subtitle = ctk.CTkLabel(
            container,
            text="Inicia sesión para continuar",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=theme.TEXT_MUTED,
        )
        subtitle.pack(pady=(0, 24))

        self._login_button = ctk.CTkButton(
            container,
            text="🔑 Iniciar sesión con Microsoft",
            width=280,
            height=40,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_BLUE,
            hover_color=theme.PRIMARY_BLUE_HOVER,
            command=self._handle_login_click,
        )
        self._login_button.pack(pady=(0, 12))

        if not is_configured():
            self._login_button.configure(state="disabled")

        # --- Área del código de dispositivo (oculta hasta que haga falta) ---
        self._code_frame = ctk.CTkFrame(container, fg_color=theme.SURFACE_WHITE, corner_radius=theme.CORNER_RADIUS)

        code_instructions = ctk.CTkLabel(
            self._code_frame,
            text="Abre esta página en tu navegador e ingresa el código:",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            wraplength=380,
        )
        code_instructions.pack(padx=16, pady=(14, 4))

        self._url_label = ctk.CTkLabel(
            self._code_frame,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.PRIMARY_BLUE,
        )
        self._url_label.pack(padx=16)

        self._code_label = ctk.CTkLabel(
            self._code_frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=26, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        self._code_label.pack(padx=16, pady=(6, 4))

        copy_code_button = ctk.CTkButton(
            self._code_frame,
            text="Copiar código",
            width=140,
            height=26,
            fg_color=theme.PRIMARY_BLUE_LIGHT,
            text_color=theme.PRIMARY_BLUE,
            hover_color=theme.BORDER_LIGHT,
            command=self._copy_code,
        )
        copy_code_button.pack(pady=(0, 14))

        self._status_label = ctk.CTkLabel(
            container,
            text="Verificando si ya iniciaste sesión antes..." if is_configured() else
            "⚠️ El login con Microsoft todavía no está configurado (falta el Client ID). "
            "Contacta al administrador del sistema para poder ingresar.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            wraplength=380,
        )
        self._status_label.pack(pady=(4, 20))

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
        self._code_label.configure(text=code)
        self._url_label.configure(text=url)
        self._code_frame.pack(pady=(0, 12))
        self._status_label.configure(text="Esperando que inicies sesión en el navegador...")
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
