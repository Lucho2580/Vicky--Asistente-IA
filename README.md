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

## Reversión completa: instalador vuelve a ser simple (sin asistente de diálogos)

El error 2819 seguía apareciendo incluso después de quitar solo el
checkbox de "abrir al finalizar" — es decir, mi hipótesis de que ese
era el problema estaba mal. En vez de seguir adivinando y haciendo
perder tiempo con instalaciones fallidas, se revirtió **todo** lo
agregado en esta área: ya no hay pantalla de licencia, ni elección de
carpeta de instalación, ni ninguna personalización de diálogos —
Windows Installer usa su comportamiento por defecto (progreso simple).
Es exactamente la misma configuración que funcionaba antes de empezar
a tocar esto.

**Esta vez la validación es mucho más sólida que en los intentos
anteriores**: se pudo compilar el `Product.wxs` completo, tal cual
queda en el repositorio, de punta a punta con herramientas WiX reales
(`wixl`/`wixl-heat`, la variante para Linux), generando un `.msi`
real y verificando sus tablas internas (`File`, `Directory`) — antes
solo se podía validar una versión "recortada a mano" del archivo,
porque las partes de interfaz personalizada no eran compatibles con
las herramientas disponibles en este entorno. Sin esas partes, la
validación ahora es completa y confiable.

Si en algún momento quieren un asistente de instalación con pantallas
(licencia, elegir carpeta, checkbox de abrir al finalizar), la forma
correcta de retomarlo es generando un log real de una instalación que
falle (`msiexec /i AsistenteIA-Setup.msi /l*v install.log`) y
compartiendo la línea con "2819" de ese log — ahí sí queda anotado el
Dialog/Control/Property exacto involucrado, algo que el simple popup
de error no muestra y que no se puede adivinar sin poder correr las
herramientas de Windows reales.

## Fix real: error LGHT0311 (caracteres fuera de la página de códigos 1252)

Error real, con causa identificada con certeza (a diferencia de los
intentos anteriores sobre el error 2819, que sí necesitaban un log de
Windows para diagnosticar bien):
```
error LGHT0311 : A string was provided with characters that are not
available in the specified database code page '1252'.
```

**Causa encontrada**: `packaging/wix/Product.wxs` estaba guardado en
UTF-8 **sin BOM** (marca de orden de bytes). Se verificó byte por
byte: los caracteres acentuados en sí ("versión", "más", línea 38,
`DowngradeErrorMessage`) son perfectamente válidos en la página de
códigos 1252 — el problema real es que, sin el BOM al inicio del
archivo, `candle.exe` puede no detectar de forma confiable que el
archivo es UTF-8 (pese a que la cabecera XML lo declara), interpreta
mal esos caracteres, y el resultado ya no encaja en ninguna página de
códigos — de ahí el error al enlazar con `light.exe`.

**Corrección**: se agregó el BOM UTF-8 (bytes `EF BB BF`) al inicio de
`Product.wxs`, y se forzó explícitamente `-Encoding utf8BOM` (en vez
de `-Encoding utf8`, cuyo comportamiento respecto al BOM varía entre
versiones de PowerShell) al generar la copia temporal
`Product.generated.wxs` en cada build, para que el BOM se preserve
también ahí. Verificado con una simulación byte por byte exacta del
proceso completo (leer con BOM → sustituir versión → volver a escribir
con BOM): el XML resultante es válido y los acentos se conservan
correctamente.

Nota para futuras ediciones de `Product.wxs`: si se abre y guarda con
un editor que no preserva BOM, hay que volver a agregarlo (ver nota en
el propio archivo).

## Fix definitivo: LGHT0311 seguía apareciendo pese al BOM

El BOM UTF-8 no fue suficiente — el error persistía exactamente en la
misma línea (`DowngradeErrorMessage`). Escaneé el archivo completo,
carácter por carácter, y confirmé que decodificado correctamente como
UTF-8 **ningún** carácter queda fuera de la página de códigos 1252 —
o sea que el contenido en sí está bien, pero algo en el pipeline real
de Windows/PowerShell (que no puedo reproducir ni depurar desde este
entorno) sigue interpretándolo mal.

En vez de seguir con teorías sobre encoding que no puedo verificar de
punta a punta, se aplicó la solución definitiva y a prueba de balas:
se **quitaron los acentos** del único texto que los tenía y termina
compilado en el instalador ("Ya existe una versión más nueva..." →
"Ya existe una version mas nueva..."). Confirmé con un escaneo
exhaustivo de TODOS los atributos del archivo (no solo ese) que no
queda ningún otro carácter no-ASCII en ningún valor compilado — así
que no importa qué esté pasando en el pipeline de codificación, no
hay ningún carácter especial que pueda fallar.

Se conservan los acentos en los **comentarios** del archivo (esos
nunca se compilan al `.msi`, no afectan nada) y en toda la interfaz
de la aplicación (Python/CustomTkinter), que no tiene esta limitación
de página de códigos — esto es exclusivo de los textos que Windows
Installer compila dentro del propio `.msi`.

## Probar el sistema de actualizaciones (fuente: GitHub Releases)

Faltaba una pieza para que esto funcione de verdad: el workflow subía
el `.msi` como "artifact" de Actions, pero eso NO es lo mismo que un
**Release** de GitHub — el sistema de actualizaciones consulta la API
pública `/releases/latest`, que solo existe si hay un Release real.

Se agregó:
1. Un paso que crea un GitHub Release real (con el `.msi` adjunto)
   automáticamente cada vez que el build viene de un tag `vX.Y.Z`
   (no en corridas manuales sin tag).
2. `ASISTENTEIA_UPDATE_SOURCE=github` y `ASISTENTEIA_UPDATE_GITHUB_REPO`
   (este último se completa solo, con `$env:GITHUB_REPOSITORY` —
   no hace falta cargarlo como secret) en el `.env` que se empaqueta.

### Cómo probarlo

1. Ya tenés instalada una versión (la que acabás de generar). Anotá
   qué tag/versión es.
2. Subí un tag NUEVO, más alto:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
3. Esperá a que termine el workflow en Actions. Al terminar, andá a la
   pestaña **Releases** de tu repo — debería haber un release nuevo
   "Asistente IA - La Vianda v1.0.1" con el `.msi` adjunto.
4. Abrí la app YA INSTALADA (la versión vieja) y andá a Configuración
   → Actualizaciones → "Buscar actualizaciones ahora" (o esperá a que
   la revise sola al iniciar). Debería aparecer el diálogo de "Nueva
   versión disponible" mostrando v1.0.1.
5. Al aceptar, descarga el nuevo `.msi` y lo instala — como no hay un
   checkbox de "abrir sola" (se quitó por el error 2819), vas a tener
   que abrirla vos manualmente después de que termine esa instalación.

## Cambio de nombre: "Vicky Consulting"

Se renombró la marca visible de la app de "Asistente IA - La Vianda" a
**"Vicky Consulting"** en todos los lugares donde aparece el nombre de
la aplicación: título de la ventana, encabezado del panel lateral,
saludo/login, página "Acerca de", nombre del producto en el
instalador (`Product.wxs`), accesos directos (menú Inicio, escritorio,
desinstalar), licencia del instalador, y comentarios/documentación.

**Se mantiene sin cambios** el nombre interno del ejecutable
(`AsistenteIA.exe`) y la carpeta de instalación en disco — cambiar eso
también implicaría tocar muchas referencias interconectadas (rutas del
instalador, PyInstaller, accesos directos) con más riesgo, y no afecta
lo que el usuario final ve (nombre de la ventana, del acceso directo,
del instalador). Si más adelante quieren renombrar también el `.exe` en
sí, es un cambio aparte que puedo hacer con cuidado.

Se dejaron sin tocar, a propósito, las menciones a "La Vianda" que
se refieren a la **empresa** como contexto (no como nombre de la app):
el placeholder del chat ("Pregúntame cualquier cosa sobre La Vianda...")
y la descripción de la tarjeta de Base de Datos ("servidor SQL Server
corporativo de La Vianda") — esas siguen hablando de la empresa
cliente, no de la marca de la aplicación.

## Logo del instalador (pendiente)

El ícono que se ve hoy en los accesos directos es el genérico de
PyInstaller (nunca se configuró un ícono propio). Falta el logo real
que el usuario va a subir — una vez que lo tenga, hace falta:
1. Convertirlo a formato `.ico` (Windows requiere ese formato
   específico para íconos de acceso directo/ejecutable, con varios
   tamaños embebidos: 16x16, 32x32, 48x48, 256x256).
2. Referenciarlo en `packaging/pyinstaller/app.spec` (para que quede
   embebido en el propio `.exe`) y en `packaging/wix/Product.wxs`
   (para el ícono que se ve en "Agregar o quitar programas").

## Logo del instalador: listo, conectado

Se generó `packaging/pyinstaller/icon.ico` a partir del logo real de
La Vianda que se compartió (PNG con fondo transparente), con los 7
tamaños que Windows necesita embebidos en un solo archivo `.ico`
(16, 24, 32, 48, 64, 128, 256 px) — se centró el logo en un lienzo
cuadrado con márgen para que no se deforme al verse en los tamaños
chicos de ícono.

Se conectó en `packaging/pyinstaller/app.spec` (`icon=...`), así que
queda embebido directo en el `.exe` cuando lo compile PyInstaller. El
`Product.wxs` del instalador ya extraía el ícono desde ese mismo
`.exe` (`Icon SourceFile="$(var.SourceDir)/AsistenteIA.exe"`), así que
el ícono en "Agregar o quitar programas" también se actualiza solo,
sin tocar nada ahí.

**No hace falta ninguna acción extra** — la próxima vez que corran el
workflow, tanto el acceso directo como el ícono del instalador van a
mostrar el logo real de La Vianda en vez del genérico de PyInstaller.

Nota: a los 16x16 (el tamaño más chico, usado en la barra de tareas),
el texto "La Vianda" deja de leerse y queda solo la forma/color —
es un comportamiento esperado con cualquier logo con texto detallado a
ese tamaño, no un defecto de la conversión.

Si en algún momento quieren que el logo también aparezca DENTRO de la
app (por ejemplo, en la pantalla de login o en "Acerca de", que hoy
usan un emoji genérico 🤖 como placeholder), es un cambio aparte que
puedo hacer.

## Colores corporativos: rojo y gris (extraídos del logo real)

Se reemplazó toda la paleta de la app (antes azules genéricos tipo
ChatGPT/Copilot) por los colores reales de La Vianda, extraídos
directamente del logo que se compartió (no adivinados a ojo):

- **Rojo**: `#D81F27` (el color dominante del logo)
- **Gris**: usado para el panel lateral (`#2C2C2C`, gris oscuro) y
  textos secundarios (`#6E6E6E`), inspirado en el gris del logo
  (`#757776`).

Se renombró también la constante `PRIMARY_BLUE` a `PRIMARY_RED` en
todo el código (antes tenía un color rojo guardado en una variable
llamada "BLUE", lo cual iba a ser confuso a futuro) — todo pasa por
`ui/theme.py`, la única fuente de verdad de colores; se verificó que
no quedó ningún código de color azul viejo escrito a mano en otro
archivo.

Los colores de estado (verde=conectado, amarillo=conectando,
rojo=error) se mantuvieron sin cambios a propósito, para no confundir
"color de marca/botón" con "color de estado/error" — son
semánticamente distintos aunque ambos usen tonos de rojo parecidos.

**Limitación conocida**: el tema base de customtkinter
(`set_default_color_theme("blue")` en `main_window.py`) sigue siendo
el preset azul que trae la librería, usado solo como resguardo para
algún detalle sin estilizar a mano (por ejemplo, el color de la
barrita de scroll). Casi todo en la app ya tiene su color explícito
definido en `theme.py` (verificado), así que el efecto residual de
ese preset debería ser mínimo — si notan algún detalle azul suelto en
algún rincón, avisen y lo cazamos puntualmente.
