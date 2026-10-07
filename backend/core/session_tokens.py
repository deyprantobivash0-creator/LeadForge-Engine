"""Opaque random tokens; only their SHA-256 digests belong in the database."""

import hashlib
import hmac
import secrets


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    if not token:
        raise ValueError("token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_session_token(token: str, token_hash: str) -> bool:
    if not token or len(token) != 43 or not token_hash:
        return False
    return hmac.compare_digest(hash_session_token(token), token_hash)
