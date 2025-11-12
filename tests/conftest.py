"""Pytest configuration and fixtures."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

# Set test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["FERNET_KEY"] = "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs="  # Mock key
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["APP_ENV"] = "testing"

from app.db import Base, get_db
from app.main import app
from app.crypto import CryptoHelper


@pytest.fixture(scope="function")
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestingSessionLocal()
    
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def crypto_helper():
    """Crypto helper for tests."""
    return CryptoHelper()
