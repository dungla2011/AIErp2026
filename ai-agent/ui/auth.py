"""
Authentication utilities for API and Web server
"""
import hashlib
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / '.env', override=True)

AUTH_PASSWORD_MD5 = os.getenv("AUTH_PASSWORD_MD5", "081904e6952d21450814cd3c465cf059")
AUTH_COOKIE_DAYS = int(os.getenv("AUTH_COOKIE_DAYS", "30"))


def hash_password(password: str) -> str:
    """Hash password using MD5"""
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(plain_password: str) -> bool:
    """Verify plain password against stored hash"""
    return hash_password(plain_password) == AUTH_PASSWORD_MD5


def get_auth_token(password: str) -> str:
    """Generate auth token (MD5 hash of password)"""
    if verify_password(password):
        return AUTH_PASSWORD_MD5
    return None
