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
from core.update_security import SignatureVerificationError, signing_enabled, verify_installer_signature
from core.version import APP_BUILD, APP_VERSION
from models.update_info import UpdateInfo

DEFAULT_TIMEOUT_SECONDS = 10
DOWNLOAD_CHUNK_SIZE = 65536


class UpdateIntegrityError(Exception):
    pass


class UpdateManager:

    def __init__(
        self,
        source: str = "custom",
        endpoint_url: str = "",
        github_repo: str = "",
        channel: str = "estable",
    ) -> None:
        self._source = source
        self._endpoint_url = endpoint_url.strip()
        self._github_repo = github_repo.strip()
        self._channel = channel

    @staticmethod
    def get_current_version() -> str:
        return APP_VERSION

    @staticmethod
    def get_current_build() -> int:
        return APP_BUILD

    def check_for_updates(self, on_result: Callable[[Optional[UpdateInfo], Optional[str]], None]) -> None:

        def worker() -> None:
            try:
                info = self._fetch_latest_version_info()
            except Exception as exc:
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
            raise RuntimeError(
                "El sistema de actualizaciones no está configurado "
                "(falta ASISTENTEIA_UPDATE_ENDPOINT en el .env)."
            )
        if not self._endpoint_url.lower().startswith("https://"):
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
            raise RuntimeError(
                "El sistema de actualizaciones no está configurado "
                "(falta ASISTENTEIA_UPDATE_GITHUB_REPO en el .env)."
            )

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

        checksum_sha256 = None
        signature = None
        if msi_asset:
            base_name = msi_asset["name"]
            raw_checksum = self._fetch_companion_asset_text(
                release, [f"{base_name}.sha256", f"{base_name}.sha256.txt"]
            )
            if raw_checksum:
                checksum_sha256 = raw_checksum.split()[0].strip().lower()

            raw_signature = self._fetch_companion_asset_text(
                release, [f"{base_name}.sig", f"{base_name}.sig.txt"]
            )
            if raw_signature:
                signature = raw_signature.strip()

        body = release.get("body") or ""
        release_notes = [line.strip("- ").strip() for line in body.splitlines() if line.strip()]

        return UpdateInfo(
            version=version,
            build=release.get("id", 0),
            download_url=download_url,
            release_notes=release_notes,
            published=release.get("published_at", "")[:10],
            mandatory=False,
            checksum_sha256=checksum_sha256,
            signature=signature,
        )

    @staticmethod
    def _fetch_companion_asset_text(release: dict, candidate_names: list) -> Optional[str]:
        candidates_lower = [name.lower() for name in candidate_names]
        assets_by_lower_name = {a.get("name", "").lower(): a for a in release.get("assets", [])}

        companion = next(
            (assets_by_lower_name[name] for name in candidates_lower if name in assets_by_lower_name),
            None,
        )
        if not companion:
            return None

        try:
            request = urllib.request.Request(companion["browser_download_url"], method="GET")
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def download_update(
        self,
        update_info: UpdateInfo,
        on_progress: Callable[[int, int, float, float], None],
        on_complete: Callable[[bool, Optional[str], Optional[str]], None],
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> None:

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

                if total_bytes and downloaded != total_bytes:
                    Path(tmp_path).unlink(missing_ok=True)
                    on_complete(False, None, f"Tamaño incompleto: se esperaban {total_bytes} bytes, llegaron {downloaded}.")
                    return

                try:
                    self._verify_integrity(tmp_path, update_info)
                except UpdateIntegrityError as exc:
                    Path(tmp_path).unlink(missing_ok=True)
                    on_complete(False, None, str(exc))
                    return

                on_complete(True, tmp_path, None)

            except Exception as exc:
                on_complete(False, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(DOWNLOAD_CHUNK_SIZE), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def _verify_integrity(cls, tmp_path: str, update_info: UpdateInfo) -> None:
        if signing_enabled():
            try:
                verify_installer_signature(tmp_path, update_info.signature)
            except SignatureVerificationError as exc:
                raise UpdateIntegrityError(f"Verificación de firma fallida: {exc}") from exc
            return

        if update_info.checksum_sha256:
            actual_checksum = cls._compute_sha256(tmp_path)
            if actual_checksum.lower() != update_info.checksum_sha256.strip().lower():
                raise UpdateIntegrityError(
                    "El archivo descargado no coincide con el checksum esperado "
                    "(posible corrupción o manipulación). No se instalará."
                )
            return

        raise UpdateIntegrityError(
            "No se pudo verificar la integridad del instalador: el servidor de "
            "actualizaciones no publicó ni firma digital ni checksum SHA-256. "
            "Por seguridad, no se instalará. Contactá al administrador del "
            "sistema de actualizaciones."
        )

    def install_update(self, installer_path: str, silent: bool = False) -> "tuple[bool, Optional[str]]":
        args = ["msiexec", "/i", installer_path]
        if silent:
            args += ["/quiet", "/norestart"]
        try:
            subprocess.Popen(args)
            return True, None
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def restart_application() -> None:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, sys.argv[0]])
