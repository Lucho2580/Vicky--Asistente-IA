# Asistente IA - La Vianda (CustomTkinter)

Interfaz moderna con **Python 3.11+ / CustomTkinter**, inspirada en
ChatGPT y Microsoft Copilot, con azul corporativo como color principal.

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

## Estructura

```
ui/                       (rol de "views/": pantallas y widgets)
    main_window.py         # Ensambla sidebar + encabezado delgado + páginas + status bar
    sidebar.py              # Menú lateral (siempre visible, botones "Próximamente")
    chat_panel.py            # Bienvenida, burbujas, "escribiendo...", entrada, historial (UI)
    status_bar.py             # Estado IA / Base de datos / Usuario
    settings_window.py        # Página de Configuración por tarjetas (SettingsPage)
    theme.py                   # Paleta de colores centralizada
services/
    conversation_service.py   # Lógica de negocio: crear, enviar, agrupar historial
database/
    conversation_store.py      # Persistencia real en SQLite (conversations.db)
    sqlserver.py / sqlite.py     # Conexiones externas (estructura lista, sin implementar)
ai/
    base_provider.py / copilot.py / openai.py   # Proveedores de IA (estructura lista)
models/
    conversation.py, message.py    # Dataclasses
config/
    settings.json, app_config.py    # Preferencias persistentes
core/
    paths.py                          # Rutas compartidas (BD, logs, config)
main.py
```