"""پایهٔ موتورها — خطای دامنه با کد HTTP پیشنهادی."""
from __future__ import annotations


class DashboardError(Exception):
    """خطای دامنه‌ای موتورها؛ پیام فارسی برای کاربر + کد HTTP برای لایهٔ API."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status
