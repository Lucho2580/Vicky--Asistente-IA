"""
Paleta de colores y constantes visuales compartidas.

Centraliza los valores de diseño (colores corporativos de La Vianda:
rojo y gris, tipografías) para que todas las vistas usen exactamente
los mismos tonos y sea sencillo ajustar el estilo global desde un
solo lugar.

Los valores de PRIMARY_RED y SIDEBAR_SELECTED se extrajeron
directamente del logo real de La Vianda (rojo #D81F27), y el resto de
la paleta se armó alrededor de ese rojo y del gris corporativo
(#757776) del mismo logo, en vez de los azules genéricos que tenía
antes esta app.
"""

# Colores principales: rojo y gris corporativos de La Vianda
PRIMARY_RED = "#D81F27"        # rojo real extraído del logo
PRIMARY_RED_HOVER = "#B01821"   # variante más oscura, para estados "hover"
PRIMARY_RED_LIGHT = "#FBE9EA"    # variante muy clara, para fondos/resaltados suaves

BACKGROUND_LIGHT = "#F6F6F6"
SURFACE_WHITE = "#FFFFFF"
BORDER_LIGHT = "#E3E3E3"

TEXT_DARK = "#2B2B2B"
TEXT_MUTED = "#6E6E6E"
TEXT_ON_PRIMARY = "#FFFFFF"

SIDEBAR_BG = "#2C2C2C"           # gris oscuro corporativo (antes azul marino)
SIDEBAR_BG_HOVER = "#3D3D3D"
SIDEBAR_TEXT = "#F2F2F2"
SIDEBAR_TEXT_DISABLED = "#8A8A8A"
SIDEBAR_SELECTED = "#D81F27"     # rojo corporativo para el ítem de navegación activo

BUBBLE_USER_BG = PRIMARY_RED
BUBBLE_USER_TEXT = "#FFFFFF"
BUBBLE_AI_BG = "#EFEFEF"
BUBBLE_AI_TEXT = "#2B2B2B"

# Colores de estado (semánticos, no de marca): se mantienen distintos
# del rojo corporativo para no confundir "botón/acento" con "error".
STATUS_GREEN = "#1F9D55"
STATUS_YELLOW = "#D9A400"
STATUS_RED = "#E5484D"

FONT_FAMILY = "Segoe UI"
FONT_SIZE_TITLE = 16
FONT_SIZE_NORMAL = 13
FONT_SIZE_SMALL = 11

CORNER_RADIUS = 12
