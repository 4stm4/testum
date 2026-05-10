# SPDX-License-Identifier: MIT
"""SQLAlchemy engine and session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from infrastructure.config import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")

_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_pool_kwargs = {} if _is_sqlite else {"pool_size": 10, "max_overflow": 20}

engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
    **_pool_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
