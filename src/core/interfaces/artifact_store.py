# SPDX-License-Identifier: MIT
"""Artifact store interface (S3/MinIO)."""
from __future__ import annotations

from typing import Protocol


class ArtifactStore(Protocol):
    def upload(self, key: str, content: str) -> str:
        """Upload text content; return the key."""
        ...

    def download(self, key: str) -> str:
        """Return content for the given key."""
        ...
