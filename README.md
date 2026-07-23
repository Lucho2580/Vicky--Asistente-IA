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
## Simplificación: solo GitHub Copilot, conexión 100% automática

Se quitó la tarjeta "COPILOT / IA" de Configuración por completo, y el
selector de motor del encabezado. Ya no existe forma de elegir Offline/
OpenAI/Gemini ni de escribir el Endpoint/API Key a mano: **GitHub
Copilot es el único motor**, y se conecta solo con lo que haya en el
`.env` (`ASISTENTEIA_AI_ENDPOINT` / `ASISTENTEIA_AI_API_KEY`), con
reintentos crecientes (10s, 15s, 20s...) hasta lograrlo — sin ningún
botón "Probar conexión" que apretar.

Bug real corregido en el camino: si el Endpoint/API Key se escribían a
mano en la tarjeta (como en la captura que compartiste), el auto-connect
nunca se disparaba, porque solo se activa cuando esos valores vienen
del `.env`/variables de entorno. Ahora, al no existir más esa tarjeta,
la única forma de configurar el motor es el `.env` — coherente con el
comportamiento de auto-conexión.

**Para que la IA conecte de verdad**, completá en tu `.env`:
```
ASISTENTEIA_AI_ENDPOINT=https://models.inference.ai.azure.com/chat/completions
ASISTENTEIA_AI_API_KEY=tu_token_real_de_github
```
(el token real no se pudo copiar de la captura porque estaba oculto
con puntos — hay que pegarlo a mano).

La tarjeta "BASE DE DATOS" y "BASE DE CONOCIMIENTO" en Configuración
siguen intactas, sin cambios.

## El modelo ya sabe quién le habla (identidad del usuario en el contexto)

Encontrado con una prueba real: al preguntar "¿cómo me llamo?", el
modelo respondía que no tenía acceso a información personal — algo
esperable, porque nunca le mandábamos ningún dato del usuario logueado.

**Corregido**: ahora cada pregunta va acompañada de un mensaje de rol
"system" con el nombre real de la persona (el mismo que inició sesión
con Microsoft), instruyendo al modelo a usarlo si le preguntan su
nombre. Verificado inspeccionando el payload real enviado al servidor:
el mensaje "system" llega primero, con el nombre correcto, seguido del
mensaje "user" con la pregunta tal cual la escribió la persona.

Si por algún motivo no hay nombre disponible (login con Microsoft no
configurado), el system prompt se ajusta solo para que el modelo
conteste con naturalidad que no tiene ese dato, en vez de inventar uno.

Aplica tanto a mensajes nuevos como a "Regenerar" (comparten el mismo
camino interno), y quedó implementado para los tres proveedores
(GitHub Copilot, OpenAI, Gemini) por consistencia, aunque solo GitHub
Copilot esté activo hoy.

## Eliminar conversaciones + páginas de Ayuda y Acerca de

### Eliminar conversaciones

Cada fila del Historial ahora tiene un ícono 🗑. Al hacer clic, pide
confirmación (diálogo nativo, no se puede deshacer) y recién ahí
elimina la conversación y todos sus mensajes de forma permanente. Si
la conversación que se borra es la que estaba abierta en ese momento,
la app vuelve sola al Home. Probado de punta a punta: crear 2
conversaciones, borrar una (confirmando), verificar que solo desaparece
esa, borrar la otra estando activa (verificar que vuelve al Home), y
confirmar que cancelar el diálogo no borra nada.

### Ayuda y Acerca de

Ambas secciones del menú lateral estaban deshabilitadas ("Próximamente")
desde el arranque del proyecto; ahora están habilitadas y con
contenido real, como una página más dentro del panel principal (igual
que Configuración — no abren ninguna ventana nueva):

- **Ayuda**: guía rápida organizada en tarjetas — cómo escribir
  (Enter/Shift+Enter, Detener), archivos de entrenamiento (📎 y carpeta
  Training), Historial (abrir y eliminar conversaciones), Copiar/
  Regenerar, y el motor de IA.
- **Acerca de**: versión de la app, usuario de la sesión actual (el
  nombre real de Microsoft si inició sesión), motor de IA activo, y
  las rutas exactas donde se guardan los datos (conversaciones, base
  de conocimiento, carpeta Training, logs) — útil para soporte técnico.

Sigue pendiente solo "Tickets", tal como estaba.

## Variables de entorno al compilar el .msi con GitHub Actions

El workflow (`.github/workflows/build-msi.yml`) ahora escribe un
`.env` real dentro del instalador, tomando los valores desde
**GitHub Actions Secrets** — así el `.msi` que se genera ya sale con
todo configurado, sin que cada usuario tenga que tocar nada.

### Cómo cargar los 4 secrets (una sola vez)

En tu repositorio de GitHub: **Settings → Secrets and variables →
Actions → New repository secret**, y creá estos 4, uno por uno:

```
ASISTENTEIA_MS_CLIENT_ID
ASISTENTEIA_MS_TENANT_ID
ASISTENTEIA_AI_ENDPOINT
ASISTENTEIA_AI_API_KEY
```

Con los valores que ya tenés en tu `.env` local. Una vez cargados, el
workflow los usa automáticamente en cada build — no hace falta tocar
el YAML.

### Por qué Secrets y no pegarlos directo en el YAML

Si los escribís directo en el archivo `.yml`, quedan visibles para
cualquiera que vea el repositorio (incluso en el historial de commits,
aunque después los borres). Los Secrets de GitHub Actions nunca se
muestran en el código ni en los logs (GitHub los enmascara
automáticamente si aparecieran por error).

### Importante: no las 4 tienen el mismo riesgo

- `ASISTENTEIA_MS_CLIENT_ID` y `ASISTENTEIA_MS_TENANT_ID` **no son
  secretas en un sentido estricto**: un Client ID de una app "pública"
  de Microsoft Entra ID (como la que usamos, sin client secret) está
  pensado para ser visible — es un identificador, no una clave.
- `ASISTENTEIA_AI_ENDPOINT` es solo una URL.
- `ASISTENTEIA_AI_API_KEY` (tu token de GitHub) **sí es una clave real**
  y hay que tratarla como tal.

### Lo que tenés que saber sobre embeber la API Key en el instalador

Usar Secrets protege el valor **durante la compilación** (no aparece
en logs ni en el repo). Pero una vez que el `.msi` está armado, ese
token queda embebido dentro del ejecutable que se reparte a todos los
usuarios — cualquiera con el instalador, con las herramientas
adecuadas, podría llegar a extraerlo. Esto es una decisión consciente,
no un descuido: para una herramienta interna con usuarios de
confianza suele ser un riesgo aceptable, pero recomiendo:

1. Que el token de GitHub tenga **el mínimo permiso posible** (solo
   acceso a GitHub Models, nada más).
2. Rotarlo cada tanto (generás uno nuevo, actualizás el Secret, volvés
   a correr el workflow).
3. Si en algún momento esto te preocupa más, la alternativa real es no
   embeber la clave en el instalador y, en cambio, distribuir el
   `.env` por separado (por ejemplo, con una política de grupo o una
   carpeta compartida de la empresa) — o pasar a una arquitectura con
   un servidor propio que guarde la clave y nunca la comparta con las
   computadoras de los usuarios (la "fase 2" de la que hablamos antes).

## Abrir la app automáticamente al terminar la instalación

Al terminar de instalar, la última pantalla del asistente ahora tiene
un checkbox **"Iniciar Asistente IA - La Vianda"** (tildado por
defecto): si el usuario deja el botón "Finish" con el checkbox
marcado, la app se abre sola apenas cierra el instalador — no hace
falta buscarla en el menú Inicio.

Esto agregó también un flujo de pantallas estándar al instalador
(Bienvenida → Licencia → Carpeta de instalación → Progreso →
Finalizar) en vez de instalar en silencio sin ninguna interfaz. La
licencia (`packaging/wix/license.rtf`) es un texto breve genérico de
uso interno — se puede reemplazar por el texto legal real de la
empresa si lo tienen.

**Nota de validación**: revisé la sintaxis del `Product.wxs`
actualizado y compilé la parte no específica de esta función con las
herramientas de WiX que tengo disponibles en este entorno (Linux); la
parte que depende de la extensión de UI de WiX (`WixUI_InstallDir`,
`WixShellExec`) solo se puede compilar con el WiX Toolset real de
Windows — es el patrón estándar y muy documentado para "abrir al
finalizar", pero la primera corrida real del workflow de GitHub
Actions es la que va a confirmar que compila sin errores. Si falla,
avisame el mensaje de error exacto del paso "Enlazar con light.exe" y
lo ajustamos.

## Windows SmartScreen / "aplicación no reconocida"

Esto **no es un bug de la app**: es el comportamiento esperado de
Windows para cualquier ejecutable sin firmar que se descarga de
internet (la app le pone una marca invisible al archivo, "Mark of the
Web", y SmartScreen la usa para decidir si te advierte o no).

### La solución real: firmar el código (Authenticode)

Hace falta comprar un **certificado de firma de código** de una
autoridad certificadora reconocida (DigiCert, Sectigo, SSL.com,
GlobalSign, etc.):

- **OV (Organization Validation)**: más barato (~USD 70-300/año), pero
  la reputación de SmartScreen se construye con el tiempo, a medida
  que más gente lo descarga y ejecuta — para una herramienta interna
  con pocos usuarios, esa reputación puede tardar en acumularse.
- **EV (Extended Validation)**: más caro (~USD 300-500+/año) y requiere
  guardar la clave privada en un token USB físico (exigencia de la
  industria desde 2023), pero da confianza **inmediata** de
  SmartScreen — sin período de espera.

Con el certificado, hay que firmar tanto el `.exe` (con `signtool.exe`
del Windows SDK) como el `.msi` final. Si en algún momento consiguen
uno, avisame y agrego el paso de firma al workflow de GitHub Actions
(necesita el archivo `.pfx` y su contraseña como 2 secrets más).

### Alternativas mientras tanto (sin costo)

1. **La más efectiva para uso interno**: repartir el instalador por un
   canal interno (carpeta compartida de la empresa, SharePoint, Teams)
   en vez de un link de descarga directa desde el navegador. Un
   archivo copiado por red interna generalmente **no recibe la marca
   "Mark of the Web"**, así que SmartScreen ni siquiera se activa. Si
   hoy lo están bajando directo desde GitHub (Actions/Releases) con el
   navegador, ahí sí se la pone.
2. Si igual aparece la advertencia: los usuarios pueden hacer clic en
   **"Más información" → "Ejecutar de todas formas"**, o click derecho
   sobre el archivo descargado → Propiedades → tildar **"Desbloquear"**
   antes de abrirlo.
3. Si Windows Defender directamente pone el archivo en cuarentena (no
   solo SmartScreen, sino el antivirus), suele ser un falso positivo
   común en ejecutables armados con PyInstaller — se puede enviar a
   Microsoft para que lo reclasifiquen:
   https://www.microsoft.com/wdsi/filesubmission

## Sistema de versionamiento y actualización automática

### Decisión de arquitectura importante

El pedido original incluía un "servidor" propio que informe la última
versión. Como todavía no existe (es infraestructura real que hay que
levantar y mantener), se implementó el `UpdateManager` para soportar
**dos fuentes intercambiables por configuración**, nunca acoplado a
una URL fija:

- **`source="custom"`**: un endpoint propio, con exactamente el JSON
  del pedido original (`version`, `build`, `mandatory`, `download_url`,
  `release_notes`, `published`, más `checksum`/`signature`/
  `min_supported_version` opcionales). Es lo que hay que usar el día
  que levanten un servidor real.
- **`source="github"`** (recomendado para arrancar sin infraestructura
  nueva): usa la API pública de GitHub Releases del propio
  repositorio — cero servidor que mantener, ya lo están usando para
  compilar el `.msi`. Limitación conocida: GitHub no tiene un campo
  nativo para `mandatory` ni `checksum`, así que esos quedan en
  `False`/`None` con esa fuente.

Se configura con las mismas variables de entorno / `.env` que el resto
de la app:
```
ASISTENTEIA_UPDATE_SOURCE=github                    # o "custom"
ASISTENTEIA_UPDATE_ENDPOINT=https://tu-servidor/api/version/latest   # si source=custom
ASISTENTEIA_UPDATE_GITHUB_REPO=tu-usuario/tu-repositorio             # si source=github
```

### Versión: única fuente de verdad

`core/version.py` (`APP_VERSION`, `APP_BUILD`, `BUILD_DATE`) es la
ÚNICA fuente de verdad — ya no hay valores de versión repetidos a mano
en otros archivos (antes había uno duplicado en `settings_window.py`,
se consolidó). En cada build disparado por un tag de git (`v1.3.2`),
el workflow de GitHub Actions **sobrescribe automáticamente** ese
archivo con la versión real del tag y el número de build (contador de
Actions), y usa esos mismos valores para versionar el propio `.msi`.
Verificado: simulé la lógica exacta del workflow y confirmé que genera
Python válido e importable con los valores correctos.

### Qué se implementó y se probó de verdad

- **`CheckForUpdates()` en segundo plano al iniciar**, sin bloquear la
  interfaz, respetando la frecuencia elegida (diaria/semanal/manual) —
  probado con casos límite de fechas.
- **Comparación semántica real de versiones** (`core/semver.py`): no
  es comparación de texto (que falla con "1.10.0" vs "1.9.0") — probado
  con esos casos exactos.
- **Diálogo de actualización**: versión instalada vs. nueva, fecha,
  notas, "Actualizar ahora" / "Recordarme más tarde" (este último
  desaparece si `mandatory=true`) — probado en ambos casos.
- **Descarga con progreso real**: porcentaje, velocidad, tamaño,
  cancelación a mitad de camino, validación de tamaño e integridad
  (SHA256) — probado con un servidor local real, incluyendo detección
  de un archivo corrupto a propósito.
- **Instalación y reinicio**: al terminar la descarga, se lanza el
  `.msi` (Windows Installer ya tiene `MajorUpgrade` configurado:
  reemplaza la versión anterior sin duplicar) y se cierra la app. Como
  la configuración, conversaciones, Base de Conocimiento y documentos
  viven en la carpeta de datos de usuario (no en la de instalación),
  **nunca se tocan durante una actualización** — ya lo garantizaba la
  arquitectura de una iteración anterior.
- **Actualización silenciosa**: preparada en `install_update(silent=True)`
  y en el modelo de configuración (`silent_updates_enabled`), pero
  deshabilitada por defecto como se pidió — falta el mecanismo de
  reinicio automático post-instalación silenciosa (sin UI que el
  usuario pueda usar para reabrir sola la app), documentado como
  siguiente paso.
- **Configuración → Actualizaciones**: buscar automáticamente (sí/no),
  buscar al iniciar (sí/no), canal (estable/beta), frecuencia
  (diaria/semanal/manual), "Buscar actualizaciones ahora".
- **Acerca de**: versión, build, fecha de compilación, última
  verificación, botones "Buscar actualizaciones" y "Ver notas de la
  versión".
- **Logging nuevo** (`core/app_logger.py`, no existía antes): errores
  de red al verificar actualizaciones se registran ahí, nunca se
  muestran como un error molesto — la app sigue funcionando con
  normalidad, tal como se pidió.

### Bug real encontrado y corregido en el camino

`install_update()` no manejaba una falla al lanzar `msiexec` (permisos,
proceso bloqueado, etc.) — quedaba una excepción sin capturar justo en
el momento crítico de actualizar. Ahora retorna `(éxito, error)` y la
app se queda funcionando con normalidad si el instalador ni siquiera
pudo lanzarse, en vez de cerrarse a ciegas.

### Clase `UpdateManager` (services/update_manager.py)

Responsabilidades claras, sin mezclar lógica de UI:
`get_current_version()`, `check_for_updates()`, `download_update()`,
`install_update()`, `restart_application()` — la comparación de
versiones vive en `core/semver.py` (reutilizable), y los diálogos en
`ui/update_dialog.py` (solo llama a estos métodos, no conoce HTTP ni
sqlite ni nada de bajo nivel).

## Corrección real: "invalid command name ... check_dpi_scaling"

Este error apareció en uso real (no solo en entorno de pruebas):
```
invalid command name "...update"
invalid command name "..._set_scaled_min_max"
invalid command name "...check_dpi_scaling"
```

**Causa raíz**: la app creaba **dos ventanas raíz de Tkinter
independientes** — una para `LoginWindow` (heredaba de `ctk.CTk`) y,
al terminar el login, la destruía y creaba OTRA raíz distinta para
`MainWindow` (que también hereda de `ctk.CTk`). Customtkinter mantiene
un rastreador interno de escala de pantalla (DPI) atado a cada raíz;
al destruir una raíz y crear otra en el mismo proceso, quedan llamadas
`after()` programadas contra un intérprete Tcl que ya no existe, y
esas llamadas fallan apenas se disparan.

**Corrección**: ahora hay una única raíz `ctk.CTk()` para toda la vida
de la aplicación. El login (`ui/login_window.py`, ahora `LoginOverlay`)
dejó de ser una ventana propia: es un `CTkFrame` que se muestra DENTRO
de la misma ventana principal, y se destruye a sí mismo (no la raíz)
al terminar, dejando lugar al resto de la interfaz en esa misma
ventana. `main.py` quedó más simple: crea `MainWindow()` una sola vez.

Verificado exhaustivamente: corrí el flujo completo (login exitoso →
navegación por todas las páginas → envío de mensajes → cierre) y busqué
explícitamente esas 3 cadenas de error en la salida completa — no
aparece ninguna. También confirmé que cada escenario corriendo en su
propio proceso (como ocurre en uso real: `python main.py` arranca un
único proceso) queda completamente limpio.

## Fix: error CNDL0103 al compilar con candle.exe

Error real que apareció al correr el workflow:
```
candle.exe : error CNDL0103 : The system cannot find the file '.0.0.4' with type 'Source'.
```

**Causa**: pasar la versión del `.msi` como parámetro `-dProductVersion=X.Y.Z.W`
directo en la línea de comandos de `candle.exe` (vía `${{ env.PRODUCT_VERSION }}`
en el workflow) hace que `candle.exe` interprete mal el valor cuando
tiene varios puntos — termina tratando parte del valor como si fuera
un archivo fuente a compilar.

**Corrección**: en vez de pasar la versión por línea de comandos, el
workflow ahora **sustituye el placeholder `Version="0.0.0.0"` directo
dentro de una copia temporal** de `Product.wxs`
(`packaging/wix/obj/Product.generated.wxs`, generada en cada build, no
versionada en git) y compila esa copia. El archivo fuente
`packaging/wix/Product.wxs` nunca se modifica — siempre queda con el
placeholder, listo para el próximo build. Se aplicó el mismo fix en
`packaging/build_msi.ps1` (build local). Verificado con una simulación
exacta del reemplazo contra el archivo real: encuentra una sola
coincidencia y el XML resultante es válido.

## Fix: error 2819 al instalar ("dialog control does not support the property")

Error real reportado durante la instalación (no en el build): al
aceptar la licencia y presionar "Next", Windows Installer mostraba
`The installer has encountered an unexpected error installing this
package... The error code is 2819`.

**Causa**: al agregar el checkbox "Iniciar Asistente IA..." en la
pantalla final, se referenció `<UIRef Id="WixUI_InstallDir" />` pero
faltó su complemento casi siempre obligatorio, `WixUI_ErrorProgressText`
— sin él, algunas propiedades de texto que otros diálogos de la
secuencia (progreso, títulos) esperan encontrar quedan sin definir,
lo que Windows Installer reporta como un control que "no soporta" una
propiedad.

**Corrección**: se agregó `<UIRef Id="WixUI_ErrorProgressText" />`
junto a `WixUI_InstallDir`. También se quitó `-sval` de `light.exe`
(suprimía TODAS las validaciones internas de WiX): con esa bandera,
un problema de autoría como este no se detecta en la compilación sino
recién en la instalación real de un usuario, que es justo lo que pasó
acá. Sin `-sval`, el próximo build va a fallar rápido y con un mensaje
claro si queda algún otro problema de este tipo, en vez de generar un
`.msi` que parece válido pero falla al instalarse.

## Se quitó el checkbox "abrir al finalizar" (seguía dando error 2819)

Dos intentos de arreglar el error 2819 sin éxito, y sin acceso a
Windows/WiX Toolset real desde este entorno para depurarlo con
certeza (solo hay una reimplementación en Linux, `wixl`, que
justamente NO soporta esta parte de WiX — no sirve para reproducir
este bug). En vez de seguir adivinando y bloqueando la instalación,
se quitó específicamente el checkbox "Iniciar Asistente IA..." de la
pantalla final (las propiedades `WIXUI_EXITDIALOGOPTIONALCHECKBOX*`,
el `CustomAction` de `WixShellExec`, y el `<Publish>` asociado) —
esa era la única pieza no estándar y nueva agregada.

**Se conserva intacto** el resto de la experiencia de instalación
(Bienvenida → Licencia → **elegir carpeta de instalación con botón
"Change..." y botón "Install"** → Progreso → Finalizar), que es la
secuencia estándar de `WixUI_InstallDir` — la misma que usan miles de
instaladores WiX sin este problema, así que no era la sospechosa.

Si más adelante quieren retomar el "abrir la app sola al finalizar",
la forma correcta de resolverlo es generar un log detallado real de
una instalación que falle:
```
msiexec /i AsistenteIA-Setup.msi /l*v install.log
```
y buscar en `install.log` la línea con "2819" — ahí Windows Installer
sí registra el nombre exacto del Dialog/Control/Property involucrado
(el popup de error no lo muestra). Con ese dato puntual se puede
corregir la causa real en vez de adivinar.
