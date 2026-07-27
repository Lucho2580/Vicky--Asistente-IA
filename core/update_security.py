"""
Verificación criptográfica de actualizaciones.

POR QUÉ ESTO IMPORTA
---------------------
Un checksum SHA-256 por sí solo NO protege contra un servidor de
actualizaciones comprometido (o un atacante que intercepta/spoofea la
respuesta JSON): si el atacante controla la respuesta, controla tanto
el instalador como el checksum "correcto" que la acompaña — coinciden
porque los generó la misma parte maliciosa. El checksum solo protege
contra corrupción accidental en la descarga (bit flips, conexión
cortada), no contra manipulación deliberada.

La única defensa real contra ese escenario es una firma digital
verificada contra una clave pública que vive DENTRO del código de la
aplicación (no se descarga del mismo canal que se quiere validar). Acá
se usa Ed25519 (rápido, firmas y claves cortas, sin parámetros
inseguros que configurar mal, a diferencia de RSA).

CÓMO GENERAR EL PAR DE CLAVES (una sola vez, fuera de este repo)
------------------------------------------------------------------
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Guardar en un lugar SEGURO, fuera del repositorio (ej. un gestor
    # de secretos / HSM / USB offline). NUNCA subir a git.
    with open("update_signing_private_key.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Esta sí va en el repo / código: es pública por diseño.
    with open("update_signing_public_key.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

CÓMO FIRMAR CADA RELEASE (con la clave privada, en CI o manualmente)
------------------------------------------------------------------
    signature = private_key.sign(installer_bytes)
    signature_b64 = base64.b64encode(signature).decode("ascii")
    # Publicar `signature_b64` en el JSON del endpoint de updates, o
    # como asset adjunto al release de GitHub (ej. "app.msi.sig").
"""
import base64
from pathlib import Path
from typing import Optional

# Clave pública embebida en la aplicación. Se reemplaza por la clave
# real generada una única vez (ver docstring del módulo) antes de
# publicar la primera versión firmada. Mientras esté vacía, la
# verificación de firma se considera "no configurada" y el sistema de
# actualizaciones cae de nuevo a exigir, como mínimo, el checksum
# (ver services/update_manager.py).
UPDATE_SIGNING_PUBLIC_KEY_PEM = ""  # ej: "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"


class SignatureVerificationError(Exception):
    """La firma no pudo verificarse (ausente, corrupta, o no coincide)."""


def signing_enabled() -> bool:
    """True si hay una clave pública configurada para verificar firmas."""
    return bool(UPDATE_SIGNING_PUBLIC_KEY_PEM.strip())


def verify_installer_signature(installer_path: str, signature_b64: Optional[str]) -> bool:
    """
    Verifica que `installer_path` fue firmado con la clave privada
    correspondiente a `UPDATE_SIGNING_PUBLIC_KEY_PEM`.

    Retorna True solo si la firma es válida. Lanza
    `SignatureVerificationError` con un mensaje legible en cualquier
    otro caso (firma ausente, clave no configurada, firma inválida,
    archivo corrupto) — nunca retorna False en silencio, para que el
    llamador no pueda "olvidarse" de chequear el resultado.
    """
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
    except Exception as exc:  # noqa: BLE001
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
