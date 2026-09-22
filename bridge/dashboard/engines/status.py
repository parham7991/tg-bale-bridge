"""موتور وضعیت — اسنپ‌شات کامل پل برای کارت‌ها و چیپ‌های داشبورد."""
from __future__ import annotations

from ..context import RuntimeCtx
from ..version import VERSION


class StatusEngine:
    def __init__(self, ctx: RuntimeCtx) -> None:
        self.ctx = ctx

    def snapshot(self) -> dict:
        ctx = self.ctx
        stats = ctx.stats()
        return {
            "ok": True,
            "mode": ctx.mode,
            "version": VERSION,
            "paused": bool(getattr(ctx.bridge, "paused", False)),
            "uptime_s": ctx.uptime_s,
            "pairs": stats.get("pairs", 0),
            "mapped": stats.get("mapped", 0),
            "dash_user": ctx.store.get("dash_auth", {}).get("user", "admin")
            if isinstance(ctx.store.get("dash_auth"), dict) else "admin",
            "bale_mode": ctx.bale_mode,
            "accounts": ctx.accounts(),
        }
