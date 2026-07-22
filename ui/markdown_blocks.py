import re
from dataclasses import dataclass
from typing import List

import customtkinter as ctk

from ui import theme

_CODE_BG = "#1E1E2E"
_CODE_FG = "#E5E5E5"
_CODE_FONT_FAMILY = "Consolas"


@dataclass
class _Block:
    kind: str  # "heading" | "code" | "list" | "table" | "paragraph"
    content: str
    level: int = 0  # solo para "heading"


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
_LIST_ITEM_TEXT_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)")
_TABLE_SEPARATOR_RE = re.compile(r"^[\s\-:|]+$")
_BOLD_INLINE_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_INLINE_RE = re.compile(r"`(.+?)`")
_FULL_BOLD_RE = re.compile(r"^\*\*(.+)\*\*$")
_FULL_CODE_RE = re.compile(r"^`(.+)`$")


def _parse_blocks(markdown_text: str) -> List[_Block]:
    lines = markdown_text.splitlines()
    blocks: List[_Block] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if line.strip() == "":
            i += 1
            continue

        # Bloque de código ```...```
        if line.strip().startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # saltar la línea de cierre ```
            blocks.append(_Block("code", "\n".join(code_lines)))
            continue

        # Encabezados
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            blocks.append(_Block("heading", heading_match.group(2).strip(), level=len(heading_match.group(1))))
            i += 1
            continue

        # Tabla: una línea con "|" seguida de una línea separadora (---|---)
        if "|" in line and i + 1 < n and _TABLE_SEPARATOR_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
            table_lines = [line]
            i += 1
            while i < n and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            blocks.append(_Block("table", "\n".join(table_lines)))
            continue

        # Lista con viñetas o numerada
        if _LIST_ITEM_RE.match(line):
            list_lines = []
            while i < n and (_LIST_ITEM_RE.match(lines[i]) or lines[i].strip() == ""):
                if lines[i].strip():
                    list_lines.append(lines[i])
                i += 1
            blocks.append(_Block("list", "\n".join(list_lines)))
            continue

        # Párrafo normal: junta líneas seguidas hasta encontrar una línea
        # vacía o el inicio de otro tipo de bloque.
        paragraph_lines = [line]
        i += 1
        while (
            i < n
            and lines[i].strip()
            and not lines[i].strip().startswith("```")
            and not _HEADING_RE.match(lines[i])
            and not _LIST_ITEM_RE.match(lines[i])
        ):
            paragraph_lines.append(lines[i])
            i += 1
        blocks.append(_Block("paragraph", " ".join(paragraph_lines)))

    return blocks


def _strip_inline_markers(text: str) -> str:
    """Quita ** y ` de texto en línea (ver limitación conocida en el docstring del módulo)."""
    text = _BOLD_INLINE_RE.sub(r"\1", text)
    text = _CODE_INLINE_RE.sub(r"\1", text)
    return text


def render_markdown(parent, markdown_text: str, text_color: str, max_width: int = 420) -> None:
    """Construye los widgets necesarios dentro de `parent` para mostrar `markdown_text`."""
    blocks = _parse_blocks(markdown_text) or [_Block("paragraph", markdown_text)]

    for block in blocks:
        if block.kind == "heading":
            _render_heading(parent, block, text_color, max_width)
        elif block.kind == "code":
            _render_code(parent, block, max_width)
        elif block.kind == "table":
            _render_table(parent, block, text_color)
        elif block.kind == "list":
            _render_list(parent, block, text_color, max_width)
        else:
            _render_paragraph(parent, block, text_color, max_width)


def _render_heading(parent, block: _Block, text_color: str, max_width: int) -> None:
    size = {1: 17, 2: 15, 3: theme.FONT_SIZE_NORMAL + 1}.get(block.level, theme.FONT_SIZE_NORMAL)
    label = ctk.CTkLabel(
        parent,
        text=_strip_inline_markers(block.content),
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=size, weight="bold"),
        text_color=text_color,
        wraplength=max_width,
        justify="left",
        anchor="w",
    )
    label.pack(fill="x", pady=(6, 2), anchor="w")


def _render_code(parent, block: _Block, max_width: int) -> None:
    code_frame = ctk.CTkFrame(parent, fg_color=_CODE_BG, corner_radius=8)
    code_frame.pack(fill="x", pady=4, anchor="w")
    code_label = ctk.CTkLabel(
        code_frame,
        text=block.content,
        font=ctk.CTkFont(family=_CODE_FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
        text_color=_CODE_FG,
        justify="left",
        anchor="w",
        wraplength=max(max_width - 24, 120),
    )
    code_label.pack(padx=10, pady=8, anchor="w")


def _render_table(parent, block: _Block, text_color: str) -> None:
    # Se omite la línea separadora (---|---) y se preserva el resto tal
    # cual, en fuente monoespaciada: es una aproximación razonable a una
    # tabla real sin construir un widget de grilla completo.
    lines = [line for line in block.content.splitlines() if not _TABLE_SEPARATOR_RE.match(line) or "-" not in line]
    table_frame = ctk.CTkFrame(parent, fg_color=theme.BACKGROUND_LIGHT, corner_radius=8)
    table_frame.pack(fill="x", pady=4, anchor="w")
    table_label = ctk.CTkLabel(
        table_frame,
        text="\n".join(lines),
        font=ctk.CTkFont(family=_CODE_FONT_FAMILY, size=max(theme.FONT_SIZE_SMALL - 1, 8)),
        text_color=text_color,
        justify="left",
        anchor="w",
    )
    table_label.pack(padx=10, pady=8, anchor="w")


def _render_list(parent, block: _Block, text_color: str, max_width: int) -> None:
    for item_line in block.content.splitlines():
        match = _LIST_ITEM_TEXT_RE.match(item_line)
        item_text = match.group(1) if match else item_line
        item_label = ctk.CTkLabel(
            parent,
            text=f"•  {_strip_inline_markers(item_text)}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL),
            text_color=text_color,
            wraplength=max(max_width - 16, 100),
            justify="left",
            anchor="w",
        )
        item_label.pack(fill="x", padx=(8, 0), pady=1, anchor="w")


def _render_paragraph(parent, block: _Block, text_color: str, max_width: int) -> None:
    stripped = block.content.strip()
    is_full_bold = bool(_FULL_BOLD_RE.match(stripped))
    is_full_code = bool(_FULL_CODE_RE.match(stripped)) and not is_full_bold

    if is_full_code:
        _render_code(parent, _Block("code", _FULL_CODE_RE.match(stripped).group(1)), max_width)
        return

    display_text = _strip_inline_markers(block.content)
    label = ctk.CTkLabel(
        parent,
        text=display_text,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold" if is_full_bold else "normal"),
        text_color=text_color,
        wraplength=max_width,
        justify="left",
        anchor="w",
    )
    label.pack(fill="x", pady=2, anchor="w")
