"""
Punto de entrada de Vicky Consulting (versión CustomTkinter).

Se crea UNA SOLA vez la ventana principal (`MainWindow`), que primero
muestra el login (con Microsoft, si está configurado) como un overlay
dentro de sí misma, y luego construye el resto de la interfaz —
nunca se crean dos ventanas raíz de Tkinter separadas (eso es lo que
causaba errores reales tipo "invalid command name ... check_dpi_scaling",
un problema conocido de customtkinter al destruir una raíz y crear
otra en el mismo proceso).

Se mantiene mínimo a propósito: toda la lógica vive en los paquetes
ui/, ai/, database/, models/ y config/.
"""
from ui.main_window import MainWindow


def main() -> None:
    app = MainWindow()  # sin display_name: muestra el login dentro de la misma ventana
    app.mainloop()


if __name__ == "__main__":
    main()
