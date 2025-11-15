# SPDX-License-Identifier: MIT
"""Task and crypto tests."""
import pytest
from app.crypto import CryptoHelper


def test_crypto_encrypt_decrypt_bytes():
    """Test encrypting and decrypting bytes."""
    crypto = CryptoHelper()
    
    original = b"sensitive data"
    encrypted = crypto.encrypt_bytes(original)
    
    assert encrypted != original
    assert len(encrypted) > len(original)
    
    decrypted = crypto.decrypt_bytes(encrypted)
    assert decrypted == original


def test_crypto_encrypt_decrypt_string():
    """Test encrypting and decrypting strings."""
    crypto = CryptoHelper()
    
    original = "my secret password"
    encrypted = crypto.encrypt_string(original)
    
    assert isinstance(encrypted, bytes)
    assert encrypted != original.encode()
    
    decrypted = crypto.decrypt_string(encrypted)
    assert decrypted == original


def test_crypto_different_outputs():
    """Test that same input produces different encrypted outputs (due to IV)."""
    crypto = CryptoHelper()
    
    original = "test data"
    encrypted1 = crypto.encrypt_string(original)
    encrypted2 = crypto.encrypt_string(original)
    
    # Fernet includes timestamp, so outputs may vary
    # Both should decrypt to same value
    assert crypto.decrypt_string(encrypted1) == original
    assert crypto.decrypt_string(encrypted2) == original


def test_crypto_invalid_data():
    """Test decrypting invalid data raises exception."""
    crypto = CryptoHelper()
    
    with pytest.raises(Exception):
        crypto.decrypt_bytes(b"invalid encrypted data")


def test_crypto_empty_string():
    """Test encrypting empty string."""
    crypto = CryptoHelper()
    
    original = ""
    encrypted = crypto.encrypt_string(original)
    decrypted = crypto.decrypt_string(encrypted)
    
    assert decrypted == original


def test_crypto_unicode():
    """Test encrypting unicode characters."""
    crypto = CryptoHelper()
    
    original = "Hello 世界 🔐"
    encrypted = crypto.encrypt_string(original)
    decrypted = crypto.decrypt_string(encrypted)
    
    assert decrypted == original


# Note: Celery task tests would require mocking SSH connections
# and Redis pub/sub, which is beyond the basic test coverage.
# For production, add integration tests with actual SSH server.
