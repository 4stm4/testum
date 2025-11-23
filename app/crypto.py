# SPDX-License-Identifier: MIT
"""Simplified cryptography helpers using base64 encoding."""
import base64


class CryptoHelper:
    """Helper class for pseudo encryption/decryption."""

    def encrypt_bytes(self, data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        # Use validate=True to ensure malformed payloads raise errors
        return base64.b64decode(encrypted_data, validate=True)

    def encrypt_string(self, data: str) -> bytes:
        return self.encrypt_bytes(data.encode("utf-8"))

    def decrypt_string(self, encrypted_data: bytes) -> str:
        return self.decrypt_bytes(encrypted_data).decode("utf-8")


# Singleton instance
crypto = CryptoHelper()
