"""نگارخانهٔ تنظیمات زمان اجرا — همهٔ حساب‌ها و پیکربندی در دیتابیس (meta) ذخیره می‌شود.

هدف: `.env` فقط به **یک** توکن (بات تلگرام) نیاز دارد؛ بقیه — سلف تلگرام، سلف بله،
ربات بله، ادمین — از داخل خود بات و با ویزارد ست می‌شود و اینجا ماندگار می‌ماند.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

log = logging.getLogger("store")


class Store:
    """لایهٔ JSON روی جدول meta دیتابیس."""

    def __init__(self, db) -> None:
        self.db = db

    # ---------- پایه ----------
    def get(self, key: str, default: Any = None) -> Any:
        raw = self.db.get_meta(f"cfg:{key}")
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        self.db.set_meta(f"cfg:{key}", json.dumps(value, ensure_ascii=False))

    def delete(self, key: str) -> None:
        self.db.set_meta(f"cfg:{key}", "")

    # ---------- دسترسی‌های سطح بالا ----------
    def admin_tg_id(self) -> int:
        v = self.get("admin_tg_id", 0)
        if isinstance(v, dict):
            return int(v.get("id") or 0)
        return int(v or 0)

    def claim_admin(self, user_id: int, username: str = "") -> bool:
        """اولین کسی که /start می‌زند ادمین می‌شود؛ False اگر قبلاً ادعا شده."""
        if self.admin_tg_id():
            return False
        self.set("admin_tg_id", {"id": int(user_id), "username": username or ""})
        return True

    def tg_api(self) -> Optional[dict]:
        return self.get("tg_api")

    def tg_self(self) -> Optional[dict]:
        return self.get("tg_self")

    def bale_self(self) -> Optional[dict]:
        return self.get("bale_self")

    def bale_bot(self) -> Optional[dict]:
        return self.get("bale_bot")

    def set_tg_api(self, api_id: int, api_hash: str) -> None:
        self.set("tg_api", {"api_id": int(api_id), "api_hash": api_hash})

    def set_tg_self(self, phone: str) -> None:
        self.set("tg_self", {"phone": phone})

    def set_bale_self(self, phone: str) -> None:
        self.set("bale_self", {"phone": phone})

    def set_bale_bot(self, token: str, me: dict) -> None:
        self.set("bale_bot", {"token": token, "me": me})

    # ---------- وضعیت نصب ----------
    def has_tg(self, cfg) -> bool:
        """سلف تلگرام آماده است؟ (نشست موجود + api creds از env یا store)"""
        api = self.tg_api() or {}
        api_id = int(getattr(cfg, "TG_API_ID", 0) or 0) or int(api.get("api_id", 0) or 0)
        api_hash = getattr(cfg, "TG_API_HASH", "") or api.get("api_hash", "")
        session = getattr(cfg, "SESSION_PATH", None)
        import pathlib

        return bool(api_id and api_hash and session
                    and pathlib.Path(str(session) + ".session").exists())

    def has_bale(self, cfg) -> bool:
        """سمت بله آماده است؟ (سلف با نشست، یا ربات با توکن از store/env)"""
        import pathlib

        if self.bale_self():
            return True
        if self.bale_bot():
            return True
        if getattr(cfg, "BALE_TOKEN", ""):
            return True
        if getattr(cfg, "BALE_MODE", "bot") == "user":
            sess = pathlib.Path(str(getattr(cfg, "BALE_SESSION", "")))
            sess = sess if sess.suffix == ".bale" else sess.with_suffix(".bale")
            return sess.exists()
        return False

    def installed(self, cfg) -> bool:
        """نصب کامل = هر دو سو آماده."""
        return self.has_tg(cfg) and self.has_bale(cfg)
