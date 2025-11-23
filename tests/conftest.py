# SPDX-License-Identifier: MIT
"""Pytest fixtures for simplified app."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.storage import storage


@pytest.fixture(autouse=True)
def reset_storage():
    storage.reset()
    yield
    storage.reset()


@pytest.fixture(scope="function")
def client(reset_storage):
    with TestClient(app) as c:
        yield c
