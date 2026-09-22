"""بافر نگهداری آخرین خطوط لاگ — برای دستور /logs بات مدیریت."""
from __future__ import annotations

import logging
from collections import deque


class RingBufferHandler(logging.Handler):
    """آخرین N رکورد لاگ را در حافظه نگه می‌دارد."""

    def __init__(self, capacity: int = 300):
        super().__init__()
        self.lines: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        try:
            self.lines.append(self.format(record))
        except Exception:
            pass

    def tail(self, n: int = 15) -> list[str]:
        n = max(1, min(int(n), 100))
        return list(self.lines)[-n:]


def install(capacity: int = 300, level: int = logging.INFO) -> RingBufferHandler:
    """هندلر را روی ریشهٔ لاگر نصب می‌کند."""
    handler = RingBufferHandler(capacity)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s",
                                           datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    return handler
