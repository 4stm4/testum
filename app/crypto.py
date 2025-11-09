"""Cryptography helpers using Fernet for symmetric encryption."""
from cryptography.fernet import Fernet
from app.config import config


class CryptoHelper:
    """Helper class for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize Fernet cipher with key from config."""
        if not config.FERNET_KEY:
            raise ValueError("FERNET_KEY is not configured")
        self._fernet = Fernet(config.FERNET_KEY.encode())

    def encrypt_bytes(self, data: bytes) -> bytes:
        """
        Encrypt bytes data.

        Args:
            data: Raw bytes to encrypt

        Returns:
            Encrypted bytes
        """
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt bytes data.

        Args:
            encrypted_data: Encrypted bytes to decrypt

        Returns:
            Decrypted raw bytes
        """
        return self._fernet.decrypt(encrypted_data)

    def encrypt_string(self, data: str) -> bytes:
        """
        Encrypt string data.

        Args:
            data: String to encrypt

        Returns:
            Encrypted bytes
        """
        return self.encrypt_bytes(data.encode("utf-8"))

    def decrypt_string(self, encrypted_data: bytes) -> str:
        """
        Decrypt to string.

        Args:
            encrypted_data: Encrypted bytes to decrypt

        Returns:
            Decrypted string
        """
        return self.decrypt_bytes(encrypted_data).decode("utf-8")


# Singleton instance
crypto = CryptoHelper()
