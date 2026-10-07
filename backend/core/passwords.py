"""Argon2id password hashing boundary for future authentication services."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_hasher = PasswordHasher(type=Type.ID, time_cost=3, memory_cost=65536,
                         parallelism=4, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    if not password or len(password) > 1024:
        raise ValueError("password must contain 1 to 1024 characters")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
