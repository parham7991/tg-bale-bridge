"""EnvParseEngine — مکانیک خواندن و تبدیل مقادیر .env (int/float/flag).

موتور روی یک نگاشت env کار می‌کند (پیش‌فرض os.environ) — برای تست کاملاً
آفلاین قابل ساخت است.
"""
from __future__ import annotations

import os


class EnvParseEngine:
    """خوانندهٔ env با پیش‌فرض‌های امن (مقدار خراب → پیش‌فرض)."""

    def __init__(self, env: dict | None = None) -> None:
        self.env = os.environ if env is None else env

    def raw(self, name: str, default: str = "") -> str:
        return self.env.get(name, default)

    def stripped(self, name: str, default: str = "") -> str:
        return self.env.get(name, default).strip()

    def int_of(self, name: str, default: int = 0) -> int:
        raw = self.env.get(name, "").strip()
        try:
            return int(raw) if raw else default
        except ValueError:
            return default

    def float_of(self, name: str, default: float) -> float:
        raw = self.env.get(name, "").strip()
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    def flag(self, name: str, default: str = "1") -> bool:
        return self.env.get(name, default).strip().lower() not in ("0", "false", "no")
