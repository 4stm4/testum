# SPDX-License-Identifier: MIT
"""Pagination helper utilities."""
from typing import Tuple

from starlette.requests import Request


def get_pagination_params(
    request: Request,
    *,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Tuple[int, int]:
    """Parse limit and offset query params with bounds checking."""

    try:
        limit = int(request.query_params.get("limit", default_limit))
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        raise ValueError("Invalid pagination parameters")

    if limit < 1:
        raise ValueError("limit must be >= 1")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit > max_limit:
        limit = max_limit

    return limit, offset
