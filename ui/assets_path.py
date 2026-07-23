"""
Ubicación de archivos dentro de ui/assets/ (hoy, el logo real de La
Vianda), de forma que funcione tanto corriendo desde código fuente
como ya compilado con PyInstaller.
"""
import os
import sys


def get_asset_path(*relative_parts: str) -> str:
    if getattr(sys, "frozen", False):
        # Compilado con PyInstaller: `sys._MEIPASS` es la forma correcta
        # y estable (funciona igual en onefile y one-folder, en
        # cualquier versión) de encontrar dónde quedaron los datos
        # empaquetados — ver packaging/pyinstaller/app.spec.
        base_dir = sys._MEIPASS
    else:
        # Corriendo desde código fuente: subir un nivel desde ui/ para
        # llegar a la raíz del proyecto.
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "ui", "assets", *relative_parts)
