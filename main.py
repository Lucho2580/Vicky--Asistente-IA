"""
Punto de entrada de Asistente IA - La Vianda (versión CustomTkinter).

Antes de mostrar la app, se muestra una pantalla de login (con
Microsoft, si está configurado; ver core/microsoft_auth.py). El
nombre real de la persona logueada se usa después en el saludo del
Home ("Buenos días, Carlos 👋") en vez del usuario de Windows.

Se mantiene mínimo a propósito: toda la lógica vive en los paquetes
ui/, ai/, database/, models/ y config/.
"""
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def main() -> None:
    def launch_main_window(display_name: str | None) -> None:
        app = MainWindow(display_name=display_name)
        app.mainloop()

    login = LoginWindow(on_complete=launch_main_window)
    login.mainloop()


if __name__ == "__main__":
    main()
