# SPDX-License-Identifier: MIT
"""Security utilities for password hashing and verification."""
import base64
import hashlib
import hmac
import os
from typing import Tuple


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 120_000


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def hash_password(password: str) -> str:
    """Hash a plain text password using PBKDF2."""

    salt = os.urandom(16)
    derived = _derive_key(password, salt, ITERATIONS)
    return "$".join(
        [
            ALGORITHM,
            str(ITERATIONS),
            base64.b64encode(salt).decode("utf-8"),
            base64.b64encode(derived).decode("utf-8"),
        ]
    )


def _parse_hash(encoded: str) -> Tuple[str, int, bytes, bytes]:
    algorithm, iterations, salt_b64, hash_b64 = encoded.split("$")
    return (
        algorithm,
        int(iterations),
        base64.b64decode(salt_b64),
        base64.b64decode(hash_b64),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""

    try:
        algorithm, iterations, salt, expected = _parse_hash(hashed_password)
    except Exception:
        return False

    if algorithm != ALGORITHM:
        return False

    candidate = _derive_key(plain_password, salt, iterations)
    return hmac.compare_digest(candidate, expected)
