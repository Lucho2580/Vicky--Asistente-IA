# -*- mode: python ; coding: utf-8 -*-
"""
Spec de PyInstaller para "Vicky Consulting".

Genera un ejecutable de Windows independiente (no requiere que el
usuario final tenga Python instalado). Este archivo debe ejecutarse
con PyInstaller en Windows (o en un runner de GitHub Actions con
windows-latest); no produce un .exe válido si se corre en Linux/macOS,
ya que PyInstaller empaqueta binarios nativos del sistema operativo
donde se ejecuta.

Uso (desde la raíz del proyecto, en Windows):
    pyinstaller --noconfirm --clean packaging/pyinstaller/app.spec

El resultado queda en dist/AsistenteIA/ (modo "one-folder", recomendado
para empaquetar con WiX/MSI en vez de "one-file").
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH es una variable que PyInstaller inyecta automáticamente en
# este archivo: apunta a la carpeta donde vive este .spec, sin importar
# desde qué directorio se invoque pyinstaller.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

APP_NAME = "AsistenteIA"

# customtkinter necesita sus assets (temas, fuentes) empaquetados como datos.
datas = collect_data_files("customtkinter")
# Nuestros propios assets (logo real para la pantalla de login) — sin
# esto, el .exe compilado no encuentra ui/assets/logo.png en tiempo de
# ejecución (queda dentro de la app, pero el análisis de PyInstaller no
# copia archivos de datos "sueltos" que no sean de una librería).
datas += [(os.path.join(PROJECT_ROOT, "ui", "assets"), "ui/assets")]
# Nota: NO se empaqueta config/settings.json aquí a propósito. La app
# genera su propia configuración y base de datos en la carpeta de datos
# de usuario (ver core/paths.py) la primera vez que se ejecuta, nunca
# dentro de la carpeta de instalación.

# Pillow (PIL): se usa directamente en ui/login_window.py para mostrar
# el logo real. El análisis estático de PyInstaller no siempre detecta
# todos sus submódulos (falló en una build real con "No module named
# 'PIL'"), así que se fuerza explícitamente acá.
hidden_imports = collect_submodules("PIL") + ["PIL._tkinter_finder"]

block_cipher = None

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # sin consola, es una app de escritorio con GUI
    icon=os.path.join(SPECPATH, "icon.ico"),  # logo de La Vianda
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
