"""AccountsEngine — دسترسی‌های سطح بالا: ادمین، api تلگرام، سلف‌ها، ربات بله.

    claim_admin → اولین /start صاحب بات می‌شود؛ False اگر قبلاً ادعا شده.
"""
from __future__ import annotations

from typing import Optional

from .types_map import admin_id_from


class AccountsEngine:
    """اکانت‌های ثبت‌شدهٔ برنامه — فقط JSON خواندن/نوشتن."""

    def __init__(self, kv) -> None:
        self.kv = kv            # JsonKVEngine

    # ───────────────────────────── ادمین ─────────────────────────────
    def admin_tg_id(self) -> int:
        return admin_id_from(self.kv.get("admin_tg_id", 0))

    def claim_admin(self, user_id: int, username: str = "") -> bool:
        """اولین کسی که /start می‌زند ادمین می‌شود؛ False اگر قبلاً ادعا شده."""
        if self.admin_tg_id():
            return False
        self.kv.set("admin_tg_id", {"id": int(user_id), "username": username or ""})
        return True

    # ───────────────────────────── اکانت‌ها ─────────────────────────────
    def tg_api(self) -> Optional[dict]:
        return self.kv.get("tg_api")

    def tg_self(self) -> Optional[dict]:
        return self.kv.get("tg_self")

    def bale_self(self) -> Optional[dict]:
        return self.kv.get("bale_self")

    def bale_bot(self) -> Optional[dict]:
        return self.kv.get("bale_bot")

    def set_tg_api(self, api_id: int, api_hash: str) -> None:
        self.kv.set("tg_api", {"api_id": int(api_id), "api_hash": api_hash})

    def set_tg_self(self, phone: str) -> None:
        self.kv.set("tg_self", {"phone": phone})

    def set_bale_self(self, phone: str) -> None:
        self.kv.set("bale_self", {"phone": phone})

    def set_bale_bot(self, token: str, me: dict) -> None:
        self.kv.set("bale_bot", {"token": token, "me": me})
