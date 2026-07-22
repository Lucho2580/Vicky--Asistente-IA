"""
Única fuente de verdad de la versión de la aplicación.

NO escribas la versión a mano en ningún otro archivo (Acerca de,
instalador, etc.) — todo el código debe importar `APP_VERSION` y
`APP_BUILD` desde acá.

En CI (GitHub Actions), este archivo se regenera automáticamente en
cada build disparado por un tag (`v1.3.2`): el workflow extrae la
versión del propio tag de git y el número de build del contador de
ejecuciones de Actions (`github.run_number`), y sobrescribe este
archivo antes de compilar — así la versión semántica del tag,
la versión embebida en el .exe, y la versión del .msi quedan siempre
sincronizadas entre sí sin mantenerlas a mano en varios lugares.

Para desarrollo local (`python main.py` sin pasar por CI), estos son
los valores por defecto.
"""
APP_VERSION = "1.0.0"      # Versión semántica: major.minor.patch
APP_BUILD = 0                # Build interno (número de ejecución de CI; 0 = build local/dev)
BUILD_DATE = "2026-01-01"    # Fecha de compilación (se sobrescribe en CI con la fecha real)
