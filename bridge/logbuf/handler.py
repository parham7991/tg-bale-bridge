"""HandlerEngine — هندلر logging روی RingEngine (امن در برابر خطای فرمت)."""
from __future__ import annotations

import logging

from .ring import RingEngine
from .types_map import DEFAULT_CAPACITY


class RingBufferHandler(logging.Handler):
    """آخرین N رکورد لاگ را در حافظه نگه می‌دارد — همان کلاس قدیمی."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        super().__init__()
        self.ring = RingEngine(capacity)

    @property
    def lines(self):
        """دسترسی مستقیم به صف (سازگاری با کد قدیمی)."""
        return self.ring.lines

    def emit(self, record: logging.LogRecord):
        try:
            self.ring.append(self.format(record))
        except Exception:
            pass  # هندلر لاگ هرگز نباید خودش استخر لاگ را بیندازد

    def tail(self, n: int = 15) -> list[str]:
        return self.ring.tail(n)
