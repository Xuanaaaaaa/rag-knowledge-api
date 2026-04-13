from __future__ import annotations


class AppException(Exception):
    def __init__(self, error: str, message: str, status_code: int = 400) -> None:
        self.error = error
        self.message = message
        self.status_code = status_code
        super().__init__(message)
