"""RuntimeCtx — دسترسی تایپ‌شده به وضعیت زندهٔ پل برای همهٔ موتورها.

به‌جای دیکشنری خام rt، هر موتور دقیقاً می‌داند چه چیزی در دسترس است:
admin/bridge/tg/bale (حالت کامل) و log_buffer/started_at (هر دو حالت بوت).
"""
from __future__ import annotations

import time
from typing import Any


class RuntimeCtx:
    """زمینهٔ اجرا — یک نمونه، بین همهٔ موتورها مشترک."""

    def __init__(self, db, store, cfg, rt: dict | None = None) -> None:
        self.db = db
        self.store = store
        self.cfg = cfg
        rt = rt or {}
        self.admin = rt.get("admin")            # پنل ادمین (resolveها) — حالت کامل
        self.bridge = rt.get("bridge")          # موتور همگام‌سازی — حالت کامل
        self.tg = rt.get("tg")                  # کلاینت سلف تلگرام
        self.bale = rt.get("bale")              # سلف/ربات بله
        self.tg_me = rt.get("tg_me") or {}
        self.bale_me = rt.get("bale_me") or {}
        self.log_buffer = rt.get("log_buffer")
        self.started_at = rt.get("started_at") or time.time()

    # ───────────────────────────── وضعیت کلی ─────────────────────────────
    @property
    def mode(self) -> str:
        """«bridge» اگر موتور همگام‌سازی بالا است، وگرنه «installer»."""
        return "bridge" if self.bridge is not None else "installer"

    @property
    def uptime_s(self) -> int:
        return int(time.time() - self.started_at)

    @property
    def bale_mode(self) -> str:
        return getattr(self.cfg, "BALE_MODE", "bot")

    def stats(self) -> dict:
        try:
            return self.db.stats()
        except Exception:
            return {"pairs": 0, "mapped": 0}

    # ───────────────────────────── حساب‌ها ─────────────────────────────
    def _clean(self, acc: Any) -> dict:
        """فقط فیلدهای نمایشی — هر توکن/راز حذف می‌شود."""
        out = dict(acc or {})
        for k in ("token", "access_hash", "phone", "phone_code_hash"):
            out.pop(k, None)
        return out

    def accounts(self) -> dict:
        """اسنپ‌شات حساب‌ها برای نمایش — بات کنترل از admin.tg_bot_info می‌آید."""
        control = {}
        if self.admin is not None:
            control = getattr(self.admin, "tg_bot_info", None) or {}
        bale_bot = dict(self.store.bale_bot().get("me") or {}) if self.store.bale_bot() else {}
        return {
            "tg_self": self._clean(self.tg_me),
            "bale": self._clean(self.bale_me),
            # بات کنترل تلگرام: از پنل ادمین دقیق‌تر است؛ اگر نبود از حالت ترکیبی
            "control_bot": self._clean(control) or self._clean(bale_bot),
            "bale_bot": self._clean(bale_bot),
        }
