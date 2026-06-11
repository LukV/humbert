"""The API's one error shape.

Every failure a route reports — missing connection, bad setup, unknown cell —
serialises as ``{"error": message}`` with a status code, so the SPA has a single
shape to read. Routes raise :class:`APIError`; the handler registered in
``create_app`` does the serialising.
"""

from __future__ import annotations


class APIError(Exception):
    """A route-level failure with a status code and a human message."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def no_connection() -> APIError:
    return APIError(400, "No active connection. Run `humbert connect <dbt-project>` first.")
