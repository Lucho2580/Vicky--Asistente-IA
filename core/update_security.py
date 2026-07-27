import base64
from pathlib import Path
from typing import Optional

UPDATE_SIGNING_PUBLIC_KEY_PEM = ""


class SignatureVerificationError(Exception):
    pass


def signing_enabled() -> bool:
    return bool(UPDATE_SIGNING_PUBLIC_KEY_PEM.strip())


def verify_installer_signature(installer_path: str, signature_b64: Optional[str]) -> bool:
    if not signing_enabled():
        raise SignatureVerificationError(
            "La verificación de firma no está configurada en esta build "
            "(falta la clave pública en core/update_security.py)."
        )

    if not signature_b64:
        raise SignatureVerificationError("El servidor de actualizaciones no publicó una firma digital.")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise SignatureVerificationError(
            "Falta el paquete 'cryptography' para verificar firmas (pip install cryptography)."
        ) from exc

    try:
        public_key = serialization.load_pem_public_key(UPDATE_SIGNING_PUBLIC_KEY_PEM.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            raise SignatureVerificationError("La clave pública embebida no es Ed25519.")
    except ValueError as exc:
        raise SignatureVerificationError(f"Clave pública embebida inválida: {exc}") from exc

    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception as exc:
        raise SignatureVerificationError(f"Firma con formato inválido (no es Base64 válido): {exc}") from exc

    installer_bytes = Path(installer_path).read_bytes()

    try:
        public_key.verify(signature, installer_bytes)
    except InvalidSignature as exc:
        raise SignatureVerificationError(
            "La firma digital del instalador NO es válida: el archivo pudo haber sido "
            "modificado o el servidor de actualizaciones no es de confianza."
        ) from exc

    return True
