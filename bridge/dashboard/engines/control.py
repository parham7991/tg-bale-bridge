"""موتور کنترل — توقف/ادامهٔ سراسری همگام‌سازی (ماندگار در دیتابیس)."""
from __future__ import annotations

from ..context import RuntimeCtx
from .base import DashboardError


class ControlEngine:
    def __init__(self, ctx: RuntimeCtx) -> None:
        self.ctx = ctx

    def _bridge(self):
        bridge = self.ctx.bridge
        if bridge is None:
            raise DashboardError("پل کامل نیست — حالت نصاب", 409)
        return bridge

    def state(self) -> bool:
        return bool(getattr(self.ctx.bridge, "paused", False))

    def pause(self) -> bool:
        bridge = self._bridge()
        bridge.paused = True
        self.ctx.db.set_meta("paused", "1")
        return True

    def resume(self) -> bool:
        bridge = self._bridge()
        bridge.paused = False
        self.ctx.db.set_meta("paused", "0")
        return False
