"""ReadinessEngine — وضعیت نصب: هر سمت آماده است؟ (فایل نشست + اعتبارنامه)"""
from __future__ import annotations

import pathlib


class ReadinessEngine:
    """بررسی آمادگی هر دو سو — از store و env (cfg) هم‌زمان می‌خواند."""

    def __init__(self, accounts) -> None:
        self.accounts = accounts    # AccountsEngine

    def has_tg(self, cfg) -> bool:
        """سلف تلگرام آماده است؟ (نشست موجود + api creds از env یا store)"""
        api = self.accounts.tg_api() or {}
        api_id = int(getattr(cfg, "TG_API_ID", 0) or 0) or int(api.get("api_id", 0) or 0)
        api_hash = getattr(cfg, "TG_API_HASH", "") or api.get("api_hash", "")
        session = getattr(cfg, "SESSION_PATH", None)
        return bool(api_id and api_hash and session
                    and pathlib.Path(str(session) + ".session").exists())

    def has_bale(self, cfg) -> bool:
        """سمت بله آماده است؟ (سلف با نشست، یا ربات با توکن از store/env)"""
        if self.accounts.bale_self():
            return True
        if self.accounts.bale_bot():
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
