"""RingEngine — مکانیک حلقهٔ نگهداری خطوط (خالص، بدون logging)."""
from __future__ import annotations

from collections import deque

from .types_map import TAIL_MAX, TAIL_MIN


class RingEngine:
    """صف حلقه‌ای با cap — tail با محدودهٔ امن [TAIL_MIN, TAIL_MAX]."""

    def __init__(self, capacity: int = 300) -> None:
        self.lines: deque[str] = deque(maxlen=max(1, int(capacity)))

    def append(self, line: str) -> None:
        self.lines.append(line)

    def tail(self, n: int = 15) -> list[str]:
        n = max(TAIL_MIN, min(int(n), TAIL_MAX))
        return list(self.lines)[-n:]

    def __len__(self) -> int:
        return len(self.lines)
