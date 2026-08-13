from cryptography.fernet import Fernet
from app.core.config import settings
import base64
import hashlib
from typing import Optional


def get_fernet() -> Fernet:
    """Return a Fernet instance. Generates a key from SECRET_KEY if ENCRYPTION_KEY is not set."""
    if settings.ENCRYPTION_KEY:
        key = settings.ENCRYPTION_KEY.encode()
    else:
        # Derive a stable 32-byte key from SECRET_KEY (for development only)
        derived = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(derived)
    return Fernet(key)


def encrypt_token(token: str) -> str:
    f = get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    f = get_fernet()
    return f.decrypt(encrypted.encode()).decode()
