from hashlib import sha256

from cryptography.fernet import Fernet

from app.core.config import settings

def camera_cipher() -> Fernet:
    key = Fernet.generate_key() if not settings.camera_encryption_key else __import__("base64").urlsafe_b64encode(
        sha256(settings.camera_encryption_key.encode()).digest()
    )
    return Fernet(key)


def encrypt_camera_url(url: str) -> str:
    return camera_cipher().encrypt(url.encode()).decode()


def decrypt_camera_url(ciphertext: str) -> str:
    return camera_cipher().decrypt(ciphertext.encode()).decode()
