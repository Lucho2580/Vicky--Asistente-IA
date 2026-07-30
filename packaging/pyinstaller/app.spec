# -*- mode: python ; coding: utf-8 -*-
"""
Spec de PyInstaller para "Vicky".

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

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

APP_NAME = "AsistenteIA"

datas = collect_data_files("webview")
datas += [(os.path.join(PROJECT_ROOT, "web_ui", "templates"), "web_ui/templates")]

hidden_imports = collect_submodules("webview")

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
    console=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
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
