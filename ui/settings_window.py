import os
import subprocess
import sys
from tkinter import filedialog

import customtkinter as ctk

from config.app_config import AppConfig
from core.paths import TRAINING_DIR
from database.sqlserver import SQLServerCredentials, SQLServerDatabase
from services.knowledge_base import UnsupportedFileTypeError
from ui import theme


class Card(ctk.CTkFrame):
    """Tarjeta reutilizable con título, descripción y contenido propio."""

    def __init__(self, master, title: str, description: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=theme.SURFACE_WHITE,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_LIGHT,
            **kwargs,
        )
        self._build_header(title, description)

    def _build_header(self, title: str, description: str) -> None:
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_NORMAL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        title_label.pack(anchor="w", padx=20, pady=(16, 2))

        if description:
            desc_label = ctk.CTkLabel(
                self,
                text=description,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_MUTED,
            )
            desc_label.pack(anchor="w", padx=20, pady=(0, 10))

    def add_field(self, label_text: str, widget_cls, **widget_kwargs):
        """Agrega una fila de campo (etiqueta + widget) al cuerpo de la tarjeta."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)

        label = ctk.CTkLabel(
            row,
            text=label_text,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
            width=140,
            anchor="w",
        )
        label.pack(side="left")

        if widget_cls is ctk.CTkOptionMenu:
            # customtkinter usa su tema azul por defecto para estos
            # colores si no se especifican — se fuerza el rojo
            # corporativo para que no quede un desplegable azul suelto.
            widget_kwargs.setdefault("fg_color", theme.PRIMARY_RED)
            widget_kwargs.setdefault("button_color", theme.PRIMARY_RED_HOVER)
            widget_kwargs.setdefault("button_hover_color", theme.PRIMARY_RED)
            widget_kwargs.setdefault("dropdown_fg_color", theme.SURFACE_WHITE)
            widget_kwargs.setdefault("dropdown_text_color", theme.TEXT_DARK)
            widget_kwargs.setdefault("dropdown_hover_color", theme.BACKGROUND_LIGHT)

        widget = widget_cls(row, **widget_kwargs)
        widget.pack(side="left", fill="x", expand=True)
        return widget

    def add_footer_spacer(self) -> None:
        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()


class SettingsPage(ctk.CTkScrollableFrame):
    """Página completa de configuración, dividida en tarjetas."""

    def __init__(
        self,
        master,
        on_db_connection_change=None,
        knowledge_base=None,
        qa_log_service=None,
        connection_log_service=None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BACKGROUND_LIGHT, corner_radius=0, **kwargs)
        self._config = AppConfig()
        self._on_db_connection_change = on_db_connection_change
        self._knowledge_base = knowledge_base
        self._qa_log_service = qa_log_service
        self._connection_log_service = connection_log_service
        self._build_database_card()
        self._build_knowledge_base_card()

    # ------------------------------------------------------------------ #
    # Tarjeta: BASE DE DATOS
    # ------------------------------------------------------------------ #
    def _build_database_card(self) -> None:
        settings = self._config.settings
        card = Card(self, "BASE DE DATOS", "Datos de conexión al servidor SQL Server corporativo de La Vianda.")
        card.pack(fill="x", padx=24, pady=12)

        self.db_server_entry = card.add_field("Servidor", ctk.CTkEntry)
        self.db_server_entry.insert(0, settings.db_server)

        self.db_name_entry = card.add_field("Base", ctk.CTkEntry)
        self.db_name_entry.insert(0, settings.db_name)

        self.db_user_entry = card.add_field("Usuario", ctk.CTkEntry)
        self.db_user_entry.insert(0, settings.db_user)

        self.db_password_entry = card.add_field("Contraseña", ctk.CTkEntry, show="•")
        self.db_password_entry.insert(0, settings.db_password)

        self.db_connection_string_entry = card.add_field("Cadena de conexión", ctk.CTkEntry)
        self.db_connection_string_entry.insert(0, settings.connection_string)

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(8, 4))

        test_button = ctk.CTkButton(
            button_row,
            text="Probar conexión",
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            command=self._test_db_connection,
        )
        test_button.pack(side="left")

        self.db_status_label = ctk.CTkLabel(
            button_row,
            text="🔴 Sin conexión",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_DARK,
        )
        self.db_status_label.pack(side="left", padx=12)

        self.db_detail_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
            wraplength=520,
            justify="left",
        )
        self.db_detail_label.pack(anchor="w", padx=20, pady=(0, 4))
        card.add_footer_spacer()

    def _test_db_connection(self) -> None:
        credentials = SQLServerCredentials(
            server=self.db_server_entry.get(),
            database=self.db_name_entry.get(),
            user=self.db_user_entry.get(),
            password=self.db_password_entry.get(),
            connection_string=self.db_connection_string_entry.get(),
        )
        db = SQLServerDatabase(credentials)
        connected, message = db.connect()
        self.db_status_label.configure(
            text="🟢 SQL Server conectado" if connected else "🔴 Sin conexión"
        )
        self.db_detail_label.configure(text=message)

        if self._connection_log_service:
            target = credentials.server or "(sin servidor)"
            self._connection_log_service.log_database_attempt(target, connected, message)

        if self._on_db_connection_change:
            self._on_db_connection_change(connected, message)

    # ------------------------------------------------------------------ #
    # Tarjeta: BASE DE CONOCIMIENTO (archivos de entrenamiento + historiales)
    # ------------------------------------------------------------------ #
    def _build_knowledge_base_card(self) -> None:
        card = Card(
            self,
            "BASE DE CONOCIMIENTO",
            "Archivos de entrenamiento con persistencia real, e historial de "
            "conexiones y de preguntas/respuestas, para consultar con el tiempo.",
        )
        card.pack(fill="x", padx=24, pady=(12, 24))

        # --- Carpeta "Training": el usuario coloca archivos ahí directamente,
        # sin tener que subirlos uno por uno desde la app ---
        training_folder_row = ctk.CTkFrame(card, fg_color="transparent")
        training_folder_row.pack(fill="x", padx=20, pady=(0, 8))

        training_label = ctk.CTkLabel(
            training_folder_row,
            text="Carpeta Training (colocá aquí tus archivos, se indexan solos):",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
            text_color=theme.TEXT_MUTED,
        )
        training_label.pack(anchor="w")

        training_path_row = ctk.CTkFrame(training_folder_row, fg_color="transparent")
        training_path_row.pack(fill="x", pady=(2, 0))

        self.training_path_entry = ctk.CTkEntry(training_path_row)
        self.training_path_entry.insert(0, str(TRAINING_DIR))
        self.training_path_entry.configure(state="disabled")
        self.training_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        open_training_button = ctk.CTkButton(
            training_path_row,
            text="Abrir carpeta",
            width=110,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            command=self._open_training_folder,
        )
        open_training_button.pack(side="left", padx=(0, 6))

        reload_training_button = ctk.CTkButton(
            training_path_row,
            text="🔄 Recargar",
            width=100,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.TEXT_MUTED,
            hover_color=theme.TEXT_DARK,
            command=self._reload_training_folder,
        )
        reload_training_button.pack(side="left")

        self.training_sync_status_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            text_color=theme.TEXT_MUTED,
        )
        self.training_sync_status_label.pack(anchor="w", padx=20, pady=(0, 8))

        # --- Archivos de entrenamiento ---
        files_header = ctk.CTkFrame(card, fg_color="transparent")
        files_header.pack(fill="x", padx=20, pady=(0, 4))

        files_title = ctk.CTkLabel(
            files_header,
            text="Archivos de entrenamiento",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        files_title.pack(side="left")

        upload_button = ctk.CTkButton(
            files_header,
            text="📎 Subir archivo manualmente",
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.PRIMARY_RED,
            hover_color=theme.PRIMARY_RED_HOVER,
            width=190,
            command=self._upload_training_file,
        )
        upload_button.pack(side="right")

        self.files_list_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.files_list_frame.pack(fill="x", padx=20, pady=(4, 8))
        self._refresh_files_list()

        # --- Historial de conexiones ---
        connections_title = ctk.CTkLabel(
            card,
            text="Historial de conexiones (IA y Base de Datos)",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        connections_title.pack(anchor="w", padx=20, pady=(8, 4))

        self.connections_log_box = ctk.CTkTextbox(
            card,
            height=90,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.BACKGROUND_LIGHT,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
        )
        self.connections_log_box.pack(fill="x", padx=20, pady=(0, 8))
        self.connections_log_box.configure(state="disabled")
        self._refresh_connections_log()

        # --- Preguntas y respuestas centralizadas ---
        qa_title = ctk.CTkLabel(
            card,
            text="Preguntas y respuestas recientes",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight="bold"),
            text_color=theme.TEXT_DARK,
        )
        qa_title.pack(anchor="w", padx=20, pady=(0, 4))

        self.qa_log_box = ctk.CTkTextbox(
            card,
            height=110,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.BACKGROUND_LIGHT,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
        )
        self.qa_log_box.pack(fill="x", padx=20, pady=(0, 4))
        self.qa_log_box.configure(state="disabled")
        self._refresh_qa_log()

        card.add_footer_spacer()

    def _open_training_folder(self) -> None:
        TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(TRAINING_DIR)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(TRAINING_DIR)], check=False)
            else:
                subprocess.run(["xdg-open", str(TRAINING_DIR)], check=False)
        except Exception:
            # Sin gestor de archivos disponible (ej. entorno de pruebas sin
            # escritorio): se ignora, no es un error crítico.
            pass

    def _reload_training_folder(self) -> None:
        if self._knowledge_base is None:
            return
        summary = self._knowledge_base.sync_training_folder()
        parts = []
        if summary["added"]:
            parts.append(f"{summary['added']} agregado(s)")
        if summary["updated"]:
            parts.append(f"{summary['updated']} actualizado(s)")
        if summary["removed"]:
            parts.append(f"{summary['removed']} eliminado(s)")
        if summary["errors"]:
            parts.append(f"{len(summary['errors'])} con error")

        self.training_sync_status_label.configure(
            text="Sin cambios en la carpeta Training." if not parts else "Sincronizado: " + ", ".join(parts)
        )
        self._refresh_files_list()

    def _upload_training_file(self) -> None:
        if self._knowledge_base is None:
            return
        file_path = filedialog.askopenfilename(
            title="Subir archivo de entrenamiento",
            filetypes=[
                ("Archivos de texto", "*.txt *.md *.csv *.json *.log"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not file_path:
            return
        try:
            self._knowledge_base.add_document(file_path)
        except UnsupportedFileTypeError:
            pass
        except Exception:  # noqa: BLE001
            pass
        self._refresh_files_list()

    def _refresh_files_list(self) -> None:
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()

        if self._knowledge_base is None:
            return

        documents = self._knowledge_base.list_documents()
        if not documents:
            empty_label = ctk.CTkLabel(
                self.files_list_frame,
                text="Todavía no hay archivos de entrenamiento subidos.",
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_MUTED,
            )
            empty_label.pack(anchor="w")
            return

        for doc in documents:
            row = ctk.CTkFrame(self.files_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            icon = "📁" if doc.is_from_training_folder else "📄"
            origin_note = " · carpeta Training" if doc.is_from_training_folder else ""
            label_text = (
                f"{icon} {doc.filename}  ·  {doc.size_bytes} bytes  ·  "
                f"{doc.uploaded_at[:16].replace('T', ' ')}{origin_note}"
            )
            file_label = ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL),
                text_color=theme.TEXT_DARK,
                anchor="w",
            )
            file_label.pack(side="left", fill="x", expand=True)

            if doc.is_from_training_folder:
                # Gestionado automáticamente por la carpeta: para quitarlo
                # hay que borrar el archivo de la carpeta Training y
                # recargar (si no, la próxima sincronización lo vuelve a
                # traer, ya que el archivo real sigue estando en disco).
                managed_label = ctk.CTkLabel(
                    row,
                    text="Gestionado por Training",
                    font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
                    text_color=theme.TEXT_MUTED,
                )
                managed_label.pack(side="right")
            else:
                remove_button = ctk.CTkButton(
                    row,
                    text="Eliminar",
                    width=70,
                    height=24,
                    fg_color=theme.STATUS_RED,
                    hover_color="#C93E42",
                    font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
                    command=lambda doc_id=doc.id: self._remove_training_file(doc_id),
                )
                remove_button.pack(side="right")

    def _remove_training_file(self, document_id: int) -> None:
        if self._knowledge_base is None:
            return
        self._knowledge_base.remove_document(document_id)
        self._refresh_files_list()

    def _refresh_connections_log(self) -> None:
        self.connections_log_box.configure(state="normal")
        self.connections_log_box.delete("1.0", "end")

        if self._connection_log_service is None:
            self.connections_log_box.configure(state="disabled")
            return

        entries = self._connection_log_service.list_recent(limit=15)
        if not entries:
            self.connections_log_box.insert("1.0", "Todavía no se probó ninguna conexión.")
        else:
            lines = []
            for entry in entries:
                icon = "🟢" if entry.success else "🔴"
                category_label = "IA" if entry.category == "ia" else "Base de Datos"
                timestamp = entry.created_at[:16].replace("T", " ")
                lines.append(f"{icon} [{timestamp}] {category_label} · {entry.target_name} — {entry.message}")
            self.connections_log_box.insert("1.0", "\n".join(lines))

        self.connections_log_box.configure(state="disabled")

    def _refresh_qa_log(self) -> None:
        self.qa_log_box.configure(state="normal")
        self.qa_log_box.delete("1.0", "end")

        if self._qa_log_service is None:
            self.qa_log_box.configure(state="disabled")
            return

        records = self._qa_log_service.list_recent(limit=15)
        if not records:
            self.qa_log_box.insert("1.0", "Todavía no hay preguntas registradas.")
        else:
            lines = []
            for record in records:
                timestamp = record.created_at[:16].replace("T", " ")
                sources = f" (fuentes: {record.source_filenames})" if record.source_filenames else ""
                lines.append(
                    f"[{timestamp}] {record.engine}{sources}\n"
                    f"  P: {record.question}\n"
                    f"  R: {record.answer[:200]}"
                )
            self.qa_log_box.insert("1.0", "\n\n".join(lines))

        self.qa_log_box.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Guardado (se llama al salir de la página, ver MainWindow)
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        self._config.update(
            db_server=self.db_server_entry.get(),
            db_name=self.db_name_entry.get(),
            db_user=self.db_user_entry.get(),
            db_password=self.db_password_entry.get(),
            connection_string=self.db_connection_string_entry.get(),
        )
