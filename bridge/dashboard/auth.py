"""موتور احراز هویت داشبورد — کاملاً جدا از HTTP.

• هش رمز: PBKDF2-HMAC-SHA256 با ۱۰۰٬۰۰۰ دور و salt تصادفی ۱۶ بایتی
• سشن‌ها: توکن تصادفی ۳۲ بایتی در حافظه + کوکی HttpOnly/SameSite=Strict (در api.py)
• مقاوم‌سازی: قفل ۶۰ ثانیه‌ای پس از ۵ ورود ناموفق به‌ازای هر IP
• اعتبارنامه در store (دیتابیس) می‌ماند — از بات تلگرام هم قابل تنظیم است.
"""
from __future__ import annotations

import hashlib
import secrets
import time


def pbkdf2(password: str, salt_hex: str, iters: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iters
    ).hex()


class AuthError(Exception):
    """خطای دامنهٔ احراز هویت (پیام فارسی، کد HTTP اختیاری)."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class AuthEngine:
    """همهٔ منطق ورود/سشن/قفل — بدون هیچ وابستگی به aiohttp."""

    PBKDF_ITERS = 100_000
    MAX_FAILS = 5
    LOCK_SECONDS = 60
    SESSION_TTL = 7 * 24 * 3600

    def __init__(self, store) -> None:
        self.store = store
        self._sessions: dict[str, float] = {}   # token → expire_at
        self._fails: dict[str, list] = {}       # ip → [count, lock_until]

    # ───────────────────────── اعتبارنامه (ذخیره‌شده) ─────────────────────────
    @property
    def record(self) -> dict | None:
        return self.store.get("dash_auth")

    def ensure_credentials(self) -> tuple[str, str | None, bool]:
        """یوزرنیم + (رمز فقط اگر تازه ساخته شد) — ساخت خودکار اولین بار."""
        rec = self.record
        if rec:
            return rec.get("user", "admin"), None, False
        user, password = "admin", secrets.token_urlsafe(6)
        self.set_credentials(user, password)
        return user, password, True

    def set_credentials(self, user: str, password: str) -> None:
        salt = secrets.token_hex(16)
        self.store.set("dash_auth", {
            "user": user, "salt": salt,
            "hash": pbkdf2(password, salt, self.PBKDF_ITERS),
            "iters": self.PBKDF_ITERS,
        })

    def change_password(self, new: str) -> None:
        if len(new) < 6:
            raise AuthError("رمز حداقل ۶ کاراکتر", 400)
        self.set_credentials(self.record.get("user", "admin") if self.record else "admin", new)

    def change_user(self, user: str) -> None:
        if not user or " " in user:
            raise AuthError("یوزرنیم نامعتبر", 400)
        self.ensure_credentials()
        rec = dict(self.record or {})
        rec["user"] = user
        self.store.set("dash_auth", rec)

    @property
    def username(self) -> str:
        return (self.record or {}).get("user", "admin")

    # ───────────────────────── ورود ─────────────────────────
    def verify(self, user: str, password: str) -> bool:
        rec = self.record
        if not rec or user != rec.get("user"):
            return False
        expected = rec.get("hash", "")
        got = pbkdf2(password, rec.get("salt", ""), rec.get("iters", self.PBKDF_ITERS))
        return secrets.compare_digest(got, expected)

    def check_lock(self, ip: str) -> bool:
        fails, until = self._fails.get(ip, [0, 0])
        return fails >= self.MAX_FAILS and time.time() < until

    def register_fail(self, ip: str) -> None:
        fails, until = self._fails.get(ip, [0, 0])
        if fails + 1 >= self.MAX_FAILS:
            self._fails[ip] = [self.MAX_FAILS, time.time() + self.LOCK_SECONDS]
        else:
            self._fails[ip] = [fails + 1, until]

    def reset_fails(self, ip: str) -> None:
        self._fails.pop(ip, None)

    # ───────────────────────── سشن‌ها ─────────────────────────
    def create_session(self) -> str:
        # پاک‌سازی سشن‌های منقضی
        now = time.time()
        for t in [t for t, exp in self._sessions.items() if exp < now]:
            self._sessions.pop(t, None)
        token = secrets.token_urlsafe(32)
        self._sessions[token] = now + self.SESSION_TTL
        return token

    def is_valid(self, token: str) -> bool:
        exp = self._sessions.get(token)
        if exp is None:
            return False
        if exp < time.time():
            self._sessions.pop(token, None)
            return False
        return True

    def drop_session(self, token: str) -> None:
        self._sessions.pop(token, None)
