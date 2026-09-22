"""موتور لاگ — دمِ بافر حلقه‌ای لاگ زنده."""
from __future__ import annotations

from ..context import RuntimeCtx


class LogsEngine:
    MAX_LINES = 300

    def __init__(self, ctx: RuntimeCtx) -> None:
        self.ctx = ctx

    def tail(self, n: int = 80) -> list[str]:
        n = max(1, min(int(n or 80), self.MAX_LINES))
        buf = self.ctx.log_buffer
        if buf is None or not hasattr(buf, "tail"):
            return []
        try:
            return list(buf.tail(n))
        except Exception:
            return []
