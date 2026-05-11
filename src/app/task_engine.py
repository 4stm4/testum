"""Task queue engine — built via the new bootstrap layer."""
from bootstrap.worker import build_engine

engine = build_engine()
backend = engine.backend  # exposed for scheduler/admin use

__all__ = ["backend", "engine"]
