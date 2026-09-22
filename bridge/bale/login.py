"""BaleLoginEngine — تمام منطق ورود (auth) سلف‌بات بله، یک‌جا و بدون تکرار.

مصرف‌نده‌ها:
    • ``login_bale.py``       → ورود تعاملی کنسولی (:meth:`run_interactive`)
    • ``bridge/wizard.py``    → ورود دومرحله‌ای داخل بات مدیریت
      (:meth:`request_code` + :meth:`validate_code`)
    • هر جایی که کلاینت aiobale از روی فایل نشست لازم باشد (:meth:`build_client`)

هَش تراکنش لاگین (transaction_hash) داخل خودِ موتور نگه داشته می‌شود؛
فایل نشست پس از تأیید کد توسط aiobale ذخیره می‌شود و رمزی روی دیسک نمی‌ماند.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Tuple

from aiobale import Client
from aiobale.enums import AuthErrors

from .session import BaleSession


class BaleLoginEngine:
    """ورود سلف‌بات بله: درخواست کد، تأیید کد، ساخت کلاینت، ورود تعاملی."""

    def __init__(self, session_file: str, phone: Optional[str] = None) -> None:
        self.session_file = str(session_file)
        self.phone = (phone or "").strip() or None
        self._txn: Optional[str] = None

    # ─────────────────────────────── نشست ───────────────────────────────
    def session_path(self) -> Path:
        """مسیر نرمال‌شدهٔ فایل نشست (پسوند ``.bale``) + ساخت پوشه در صورت نیاز."""
        p = BaleSession.session_path(self.session_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def build_client(self, phone: Optional[str] = None) -> Client:
        """کلاینت aiobale از روی فایل نشست — برای ورود یا استفادهٔ مستقیم."""
        return Client(
            session_file=str(self.session_path()),
            phone_number=phone or self.phone,
        )

    # ───────────────────── ورود دومرحله‌ای (ویزارد) ─────────────────────
    async def request_code(self, phone: str, timeout: float = 45.0) -> Tuple[bool, str]:
        """مرحلهٔ ۱: ارسال کد به شمارهٔ بله؛ تراکنش داخل موتور ذخیره می‌شود."""
        try:
            client = self.build_client(phone=phone)
            resp = await asyncio.wait_for(
                client.start_phone_auth(int(phone)), timeout=timeout)
        except Exception as e:  # شبکه، تایم‌اوت، شمارهٔ نامعتبر…
            return False, f"{type(e).__name__}: {str(e)[:150]}"
        if isinstance(resp, AuthErrors):
            return False, f"خطای بله: {resp.name}"
        txn = getattr(resp, "transaction_hash", None)
        if not txn:
            return False, "پاسخ نامعتبر سرور"
        self._txn = str(txn)
        return True, "کد ارسال شد"

    async def validate_code(self, code: str, timeout: float = 45.0) -> Tuple[bool, str]:
        """مرحلهٔ ۲: تأیید کد پیامکی؛ نشست در همان فایل ذخیره می‌شود."""
        if not self._txn:
            return False, "اول شماره را بفرستید"
        try:
            client = self.build_client()
            resp = await asyncio.wait_for(
                client.validate_code(code, self._txn), timeout=timeout)
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:150]}"
        if isinstance(resp, AuthErrors):
            return False, f"خطای بله: {resp.name}"
        self._txn = None
        return True, "نشست ذخیره شد"

    @property
    def pending(self) -> bool:
        """آیا یک ورود نیمه‌تمام (کد ارسال‌شده) در جریان است؟"""
        return self._txn is not None

    # ─────────────────── ورود تعاملی کنسولی (اسکریپت) ───────────────────
    def run_interactive(self) -> int:
        """همان جریان ``login_bale.py`` — ورود از طریق ترمینال."""
        print("=" * 56)
        print("  ورود به حساب کاربری بله (سلف‌بات با aiobale)")
        print("=" * 56)
        print(f"فایل نشست: {self.session_path()}")
        if self.phone:
            print(f"شماره تلفن: {self.phone}")
        else:
            print("شماره تلفن را هنگام درخواست وارد کنید (BALE_PHONE هم قابل تنظیم است).")
        print("کد پیامکی را وارد کنید… (خروج: Ctrl+C)")
        print()

        client = self.build_client()
        try:
            client.run()
        except KeyboardInterrupt:
            print("\nلغو شد.")
            return 1
        print()
        print("✔ ورود موفق — نشست ذخیره شد.")
        print("  حالا BALE_MODE=user را در .env بگذارید و main.py را اجرا کنید.")
        return 0
