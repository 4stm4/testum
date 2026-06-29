# SPDX-License-Identifier: MIT
"""Security utilities for password hashing and verification."""
import base64
import hashlib
import hmac
import os
from typing import Tuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_argon2 = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# ── Argon2id (current) ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _argon2.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$argon2"):
        try:
            return _argon2.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # ── Legacy PBKDF2-SHA256 (migrate on next login via rehash_if_needed) ────
    return _pbkdf2_verify(plain_password, hashed_password)


def rehash_if_needed(plain_password: str, hashed_password: str) -> str | None:
    """Return a fresh Argon2id hash if the stored hash uses a legacy scheme, else None."""
    if not hashed_password.startswith("$argon2"):
        return hash_password(plain_password)
    if _argon2.check_needs_rehash(hashed_password):
        return hash_password(plain_password)
    return None


# ── Legacy PBKDF2-SHA256 ──────────────────────────────────────────────────────

_PBKDF2_ALGORITHM = "pbkdf2_sha256"


def _pbkdf2_derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _pbkdf2_parse(encoded: str) -> Tuple[str, int, bytes, bytes]:
    algorithm, iterations, salt_b64, hash_b64 = encoded.split("$")
    return (
        algorithm,
        int(iterations),
        base64.b64decode(salt_b64),
        base64.b64decode(hash_b64),
    )


def _pbkdf2_verify(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt, expected = _pbkdf2_parse(hashed_password)
    except Exception:
        return False
    if algorithm != _PBKDF2_ALGORITHM:
        return False
    candidate = _pbkdf2_derive(plain_password, salt, iterations)
    return hmac.compare_digest(candidate, expected)
