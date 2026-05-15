# SPDX-License-Identifier: MIT
"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")

# psycopg3 uses the "psycopg" dialect name; rewrite bare postgresql:// URLs
# so SQLAlchemy doesn't fall back to the removed psycopg2 driver.
def _sync_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

# Create engine
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_pool_kwargs = {} if _is_sqlite else {"pool_size": 10, "max_overflow": 20}

engine = create_engine(
    _sync_url(config.DATABASE_URL),
    pool_pre_ping=True,
    connect_args=_connect_args,
    **_pool_kwargs,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
