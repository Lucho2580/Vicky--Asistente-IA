"""
UpdateManager: verificación, descarga e instalación de actualizaciones.

Soporta dos "fuentes" de información de versión, intercambiables por
configuración (nunca acoplado a una URL fija):

    - "custom": un endpoint propio que devuelve exactamente el JSON
      {"version": "...", "build": N, "mandatory": bool,
       "download_url": "...", "release_notes": [...], "published": "..."}
      (el formato pensado para un servidor propio, hoy o a futuro).

    - "github": usa la API pública de GitHub Releases del propio
      repositorio (sin necesidad de mantener ningún servidor extra),
      tomando la versión del tag y el .msi adjunto al release como
      `download_url`. Limitación conocida: GitHub no tiene un campo
      nativo para "mandatory" ni "checksum" — quedan en False/None
      salvo que se agregue una convención propia más adelante.

No mezcla lógica de UI: esta clase no crea ventanas ni widgets: solo
llama callbacks (`on_result`, `on_progress`, `on_complete`) que la UI
decide cómo mostrar.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from core.semver import is_newer
from core.version import APP_BUILD, APP_VERSION
from models.update_info import UpdateInfo

DEFAULT_TIMEOUT_SECONDS = 10
DOWNLOAD_CHUNK_SIZE = 65536  # 64 KB por lectura, para poder reportar progreso real


class UpdateManager:
    """Verifica, descarga e instala actualizaciones de la aplicación."""

    def __init__(
        self,
        source: str = "custom",
        endpoint_url: str = "",
        github_repo: str = "",
        channel: str = "estable",
    ) -> None:
        """
        source: "custom" (endpoint propio) o "github" (GitHub Releases).
        endpoint_url: URL completa del endpoint propio (solo si source="custom").
        github_repo: "usuario/repositorio" (solo si source="github").
        channel: "estable" | "beta" — en "github", beta incluye pre-releases.
        """
        self._source = source
        self._endpoint_url = endpoint_url.strip()
        self._github_repo = github_repo.strip()
        self._channel = channel

    # ------------------------------------------------------------------ #
    # Versión actual (siempre desde core/version.py, nunca hardcodeada)
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_current_version() -> str:
        return APP_VERSION

    @staticmethod
    def get_current_build() -> int:
        return APP_BUILD

    # ------------------------------------------------------------------ #
    # 1) Verificar actualizaciones (en segundo plano, nunca bloquea la UI)
    # ------------------------------------------------------------------ #
    def check_for_updates(self, on_result: Callable[[Optional[UpdateInfo], Optional[str]], None]) -> None:
        """
        Consulta el servidor en un hilo aparte. Llama a
        `on_result(update_info, error)` cuando termina:
            - Hay una versión más nueva  -> (UpdateInfo, None)
            - Ya está actualizado         -> (None, None)
            - Falló la consulta           -> (None, "mensaje de error")

        Nunca lanza una excepción hacia afuera: sin internet o con el
        servidor caído, se informa el error para loguearlo, pero jamás
        debe impedir usar la aplicación.
        """

        def worker() -> None:
            try:
                info = self._fetch_latest_version_info()
            except Exception as exc:  # noqa: BLE001 - cualquier fallo de red se reporta, no se propaga
                on_result(None, str(exc))
                return

            if info is None:
                on_result(None, "El servidor de actualizaciones no devolvió una versión válida.")
                return

            if is_newer(info.version, APP_VERSION):
                on_result(info, None)
            else:
                on_result(None, None)

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_latest_version_info(self) -> Optional[UpdateInfo]:
        if self._source == "github":
            return self._fetch_from_github()
        return self._fetch_from_custom_endpoint()

    def _fetch_from_custom_endpoint(self) -> Optional[UpdateInfo]:
        if not self._endpoint_url:
            return None
        if not self._endpoint_url.lower().startswith("https://"):
            # No se descargan/consultan instaladores desde orígenes no HTTPS.
            raise ValueError("El endpoint de actualizaciones debe ser HTTPS.")

        with urllib.request.urlopen(self._endpoint_url, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))

        return UpdateInfo(
            version=str(data.get("version", "")),
            build=int(data.get("build", 0)),
            download_url=str(data.get("download_url", "")),
            release_notes=list(data.get("release_notes", [])),
            published=str(data.get("published", "")),
            mandatory=bool(data.get("mandatory", False)),
            checksum_sha256=data.get("checksum") or data.get("checksum_sha256"),
            signature=data.get("signature"),
            min_supported_version=data.get("min_supported_version"),
        )

    def _fetch_from_github(self) -> Optional[UpdateInfo]:
        if not self._github_repo:
            return None

        if self._channel == "beta":
            url = f"https://api.github.com/repos/{self._github_repo}/releases"
        else:
            url = f"https://api.github.com/repos/{self._github_repo}/releases/latest"

        headers = {"Accept": "application/vnd.github+json"}
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))

        release = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
        if not release:
            return None

        tag_name = release.get("tag_name", "")
        version = tag_name.lstrip("vV")

        msi_asset = next(
            (a for a in release.get("assets", []) if a.get("name", "").lower().endswith(".msi")),
            None,
        )
        download_url = msi_asset["browser_download_url"] if msi_asset else ""

        body = release.get("body") or ""
        release_notes = [line.strip("- ").strip() for line in body.splitlines() if line.strip()]

        return UpdateInfo(
            version=version,
            build=release.get("id", 0),  # GitHub no tiene "build": se usa el id del release como referencia
            download_url=download_url,
            release_notes=release_notes,
            published=release.get("published_at", "")[:10],
            mandatory=False,  # GitHub Releases no tiene este campo nativo
            checksum_sha256=None,
        )

    # ------------------------------------------------------------------ #
    # 2) Descargar el instalador (con progreso, velocidad, cancelación)
    # ------------------------------------------------------------------ #
    def download_update(
        self,
        update_info: UpdateInfo,
        on_progress: Callable[[int, int, float, float], None],
        on_complete: Callable[[bool, Optional[str], Optional[str]], None],
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Descarga `update_info.download_url` a un archivo temporal, en un
        hilo aparte.

        on_progress(bytes_descargados, bytes_totales, velocidad_bytes_seg, porcentaje)
        on_complete(exito, ruta_del_archivo_o_None, error_o_None)
        """

        def worker() -> None:
            if not update_info.download_url.lower().startswith("https://"):
                on_complete(False, None, "El instalador debe descargarse por HTTPS.")
                return

            try:
                request = urllib.request.Request(update_info.download_url, method="GET")
                with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                    total_bytes = int(response.headers.get("Content-Length", 0))

                    fd, tmp_path = tempfile.mkstemp(suffix=".msi", prefix="AsistenteIA-update-")
                    downloaded = 0
                    start_time = time.time()

                    with open(fd, "wb") as tmp_file:
                        while True:
                            if should_cancel and should_cancel():
                                on_complete(False, None, "Descarga cancelada por el usuario.")
                                Path(tmp_path).unlink(missing_ok=True)
                                return

                            chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                            if not chunk:
                                break
                            tmp_file.write(chunk)
                            downloaded += len(chunk)

                            elapsed = max(time.time() - start_time, 0.001)
                            speed = downloaded / elapsed
                            percent = (downloaded / total_bytes * 100) if total_bytes else 0.0
                            on_progress(downloaded, total_bytes, speed, percent)

                # Validar tamaño: si el servidor anticipó un Content-Length,
                # debe coincidir con lo efectivamente descargado.
                if total_bytes and downloaded != total_bytes:
                    Path(tmp_path).unlink(missing_ok=True)
                    on_complete(False, None, f"Tamaño incompleto: se esperaban {total_bytes} bytes, llegaron {downloaded}.")
                    return

                # Validar integridad (si el servidor publicó un checksum).
                if update_info.checksum_sha256:
                    actual_checksum = self._compute_sha256(tmp_path)
                    if actual_checksum.lower() != update_info.checksum_sha256.lower():
                        Path(tmp_path).unlink(missing_ok=True)
                        on_complete(False, None, "El archivo descargado no coincide con el checksum esperado (posible corrupción).")
                        return

                on_complete(True, tmp_path, None)

            except Exception as exc:  # noqa: BLE001
                on_complete(False, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(DOWNLOAD_CHUNK_SIZE), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ------------------------------------------------------------------ #
    # 3) Instalar y reiniciar
    # ------------------------------------------------------------------ #
    def install_update(self, installer_path: str, silent: bool = False) -> "tuple[bool, Optional[str]]":
        """
        Lanza el instalador y deja que Windows Installer se encargue del
        resto (el MSI ya tiene MajorUpgrade configurado: reemplaza la
        versión anterior sin duplicar, y los datos del usuario viven en
        la carpeta de datos de usuario, no en la carpeta de instalación
        — nunca se tocan durante una actualización).

        Modo normal (silent=False): se abre la interfaz del instalador
        (con nuestra pantalla de "Finalizar" que ya incluye la opción de
        reabrir la app sola). Modo silencioso (preparado, deshabilitado
        por defecto): quedaría pendiente un mecanismo de reinicio
        automático aparte, ya que el proceso actual ya habrá terminado
        para cuando el instalador silencioso concluya.

        Retorna (éxito, error_o_None): lanzar el instalador puede
        fallar (ej. msiexec bloqueado, permisos, disco lleno) y no debe
        tirar una excepción sin controlar justo en el momento crítico
        de actualizar.
        """
        args = ["msiexec", "/i", installer_path]
        if silent:
            args += ["/quiet", "/norestart"]
        try:
            subprocess.Popen(args)
            return True, None
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    @staticmethod
    def restart_application() -> None:
        """
        Vuelve a abrir la aplicación (usado en el modo silencioso a
        futuro; en el modo normal, el propio instalador ya reabre la
        app si el usuario deja tildado "Iniciar Asistente IA...").
        """
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, sys.argv[0]])
