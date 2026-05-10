# SPDX-License-Identifier: MIT
"""Fernet-based symmetric encryption."""
from cryptography.fernet import Fernet
from infrastructure.config import config


class CryptoHelper:
    def __init__(self) -> None:
        if not config.FERNET_KEY:
            raise ValueError("FERNET_KEY is not configured")
        self._fernet = Fernet(config.FERNET_KEY.encode())

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        return self._fernet.decrypt(encrypted_data)

    def encrypt_string(self, data: str) -> bytes:
        return self.encrypt_bytes(data.encode("utf-8"))

    def decrypt_string(self, encrypted_data: bytes) -> str:
        return self.decrypt_bytes(encrypted_data).decode("utf-8")


crypto = CryptoHelper()
