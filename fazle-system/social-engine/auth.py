# ============================================================
# Fazle Social Engine — Credential Encryption & Auth
# Encrypts/decrypts social platform credentials in database
# ============================================================
import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("fazle-social-engine")

_ENCRYPTION_KEY = os.environ.get("SOCIAL_ENCRYPTION_KEY", "")


def _get_fernet() -> Fernet:
    """Derive a Fernet key from SOCIAL_ENCRYPTION_KEY env var."""
    if not _ENCRYPTION_KEY:
        raise RuntimeError("SOCIAL_ENCRYPTION_KEY not configured")
    key = base64.urlsafe_b64encode(hashlib.sha256(_ENCRYPTION_KEY.encode()).digest())
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_secret(value: str) -> str:
    """Return masked version of a secret for safe display."""
    if not value or len(value) < 8:
        return "****"
    return value[:4] + "****" + value[-4:]
