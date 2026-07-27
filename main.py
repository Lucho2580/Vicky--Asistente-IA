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
from core.env_config import consume_and_scrub_embedded_ai_api_key
from ui.main_window import MainWindow


def main() -> None:
    # Reduce la ventana de exposición de la API Key embebida por el
    # instalador (ver core/env_config.py para el detalle): tiene que
    # correr ANTES de que cualquier otra cosa (AppConfig, proveedores
    # de IA) lea la configuración.
    consume_and_scrub_embedded_ai_api_key()

    app = MainWindow()  # sin display_name: muestra el login dentro de la misma ventana
    app.mainloop()


if __name__ == "__main__":
    main()
