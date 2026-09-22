"""Store — نمای سازگاری نگارخانهٔ تنظیمات زمان اجرا (ریشهٔ ترکیب بستهٔ runcfg).

سطح عمومی دقیقاً مثل قبل: ``Store(db)`` با ``get/set/delete``، دسترسی‌های
اکانت‌ها (``tg_api/tg_self/bale_self/bale_bot`` + setterها)، ``claim_admin`` و
``has_tg/has_bale/installed`` — اما داخل، هر بخش به موتور خودش تفویض می‌شود:

    types_map.py  → پیشوند کلید + استخراج شناسه ادمین
    kvstore.py    → JsonKVEngine: لایهٔ JSON روی meta
    accounts.py   → AccountsEngine: ادمین + اکانت‌ها
    readiness.py  → ReadinessEngine: وضعیت نصب هر دو سو
"""
from __future__ import annotations

from .accounts import AccountsEngine
from .kvstore import JsonKVEngine
from .readiness import ReadinessEngine


class Store:
    """لایهٔ JSON روی جدول meta دیتابیس — همهٔ اکانت‌ها و پیکربندی زمان اجرا."""

    def __init__(self, db) -> None:
        self.db = db
        # ── موتورها ──
        self.kv = JsonKVEngine(db)
        self.accounts = AccountsEngine(self.kv)
        self.readiness = ReadinessEngine(self.accounts)

    # ---------- پایه ----------
    def get(self, key: str, default=None):
        return self.kv.get(key, default)

    def set(self, key: str, value) -> None:
        self.kv.set(key, value)

    def delete(self, key: str) -> None:
        self.kv.delete(key)

    # ---------- دسترسی‌های سطح بالا ----------
    def admin_tg_id(self) -> int:
        return self.accounts.admin_tg_id()

    def claim_admin(self, user_id: int, username: str = "") -> bool:
        return self.accounts.claim_admin(user_id, username)

    def tg_api(self):
        return self.accounts.tg_api()

    def tg_self(self):
        return self.accounts.tg_self()

    def bale_self(self):
        return self.accounts.bale_self()

    def bale_bot(self):
        return self.accounts.bale_bot()

    def set_tg_api(self, api_id: int, api_hash: str) -> None:
        self.accounts.set_tg_api(api_id, api_hash)

    def set_tg_self(self, phone: str) -> None:
        self.accounts.set_tg_self(phone)

    def set_bale_self(self, phone: str) -> None:
        self.accounts.set_bale_self(phone)

    def set_bale_bot(self, token: str, me: dict) -> None:
        self.accounts.set_bale_bot(token, me)

    # ---------- وضعیت نصب ----------
    def has_tg(self, cfg) -> bool:
        return self.readiness.has_tg(cfg)

    def has_bale(self, cfg) -> bool:
        return self.readiness.has_bale(cfg)

    def installed(self, cfg) -> bool:
        return self.readiness.installed(cfg)


__all__ = ["Store"]
