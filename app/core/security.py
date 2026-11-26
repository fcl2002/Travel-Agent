"""Password hashing and verification, independent of HTTP and persistence."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Hash the exact password with Argon2id and a newly generated random salt."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
