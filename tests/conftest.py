"""Pytest configuration and fixtures."""
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["FERNET_KEY"] = "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs="  # Mock key
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["APP_ENV"] = "testing"

import app.db as app_db
from app import models  # noqa: F401 - ensure models are imported for table creation
from app.config import config
from app.crypto import CryptoHelper
from app.db import Base, get_db
from app.main import app, create_jwt_token
from app.models import User, UserRole
from app.security import hash_password


@pytest.fixture(scope="function")
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    original_session_local = app_db.SessionLocal
    app_db.SessionLocal = TestingSessionLocal
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    if hasattr(app, "dependency_overrides"):
        app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    yield session

    if hasattr(app, "dependency_overrides") and get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

    app_db.SessionLocal = original_session_local
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client."""
    admin_user = User(
        username=config.ADMIN_USERNAME,
        hashed_password=hash_password(config.ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    test_db.add(admin_user)
    test_db.commit()
    test_db.refresh(admin_user)

    with TestClient(app) as c:
        token = create_jwt_token(str(admin_user.id), admin_user.username, admin_user.role)
        c.cookies.set("access_token", token)
        yield c

    test_db.close()


@pytest.fixture
def crypto_helper():
    """Crypto helper for tests."""
    return CryptoHelper()
