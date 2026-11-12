import hashlib
import hmac
import json

from app.core.security import decrypt_camera_url, encrypt_camera_url

# The existing Fernet helper is reused; its name is historical, it encrypts any short string.


def encrypt_credentials(values: dict[str, str]) -> str:
    return encrypt_camera_url(json.dumps(values))


def decrypt_credentials(ciphertext: str) -> dict[str, str]:
    return json.loads(decrypt_camera_url(ciphertext)) if ciphertext else {}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hmac_sha256_hex(secret: str, raw: bytes) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def mask(value: str) -> str:
    return "••••" + value[-4:] if len(value) > 6 else "••••"
