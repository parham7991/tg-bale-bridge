"""TgLoginEngine — تمام منطق ورود سلف تلگرام، یک‌جا و بدون تکرار.

جریان دومرحله‌ای (+رمز دوم) که ویزارد داخل بات مدیریت اجرا می‌کند:
    request_code → sign_in → (در صورت 2FA) password
کلاینتِ در جریانِ ورود و phone_code_hash داخل خود موتور نگه داشته می‌شود
(قبلاً در state ویزارد ذخیره می‌شد).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from .gateway import TgSelfGateway

logger = logging.getLogger("bridge.tguser.login")

MISSING_SESSION_MSG = "نشست از دست رفت — از اول (دکمه 📱)"
MISSING_PW_MSG = "نشست از دست رفت"


class TgLoginEngine:
    """ورود سلف تلگرام: درخواست کد، تأیید کد، رمز دوم."""

    def __init__(self, cfg: Any, store: Any = None) -> None:
        self.cfg = cfg
        self.store = store
        # chat_id → {"client", "phone", "code_hash"}
        self._pending: Dict[Any, Dict[str, Any]] = {}

    # ───────────────────────── مرحلهٔ ۱: کد ─────────────────────────
    async def request_code(self, chat_id, phone: str,
                           api_id: Any = None, api_hash: Any = None
                           ) -> Tuple[bool, str]:
        aid, ahash = TgSelfGateway.resolve_credentials(
            self.cfg, self.store, api_id=api_id, api_hash=api_hash)
        if not aid or not ahash:
            return False, "api_id/api_hash نامعتبر"
        self.cfg.TG_API_ID, self.cfg.TG_API_HASH = aid, ahash

        from .session import TgSelfSession

        client = TgSelfSession.build(self.cfg.SESSION_PATH, aid, ahash)
        code_hash = None
        if not await TgSelfSession.connect_authorized(client):
            try:
                sent = await client.send_code_request(phone)
            except Exception as e:
                return False, f"{type(e).__name__}: {str(e)[:150]}"
            code_hash = getattr(sent, "phone_code_hash", None)
        self._pending[chat_id] = {
            "client": client, "phone": phone, "code_hash": code_hash}
        return True, "کد ارسال شد"

    # ───────────────────────── مرحلهٔ ۲: کد ─────────────────────────
    async def sign_in(self, chat_id, code: str) -> Tuple[Any, str]:
        p = self._pending.get(chat_id)
        if p is None:
            return False, MISSING_SESSION_MSG
        from telethon.errors import SessionPasswordNeededError

        try:
            await p["client"].sign_in(
                phone=p["phone"], code=code, phone_code_hash=p["code_hash"])
        except SessionPasswordNeededError:
            return "need_password", ""       # کلاینت برای مرحلهٔ رمز می‌ماند
        except Exception as e:
            return False, str(e)[:150]       # کد اشتباه → تلاش دوباره
        return True, await self._finish(chat_id, with_first_name=True)

    # ─────────────────────── مرحلهٔ ۳: رمز دوم ───────────────────────
    async def password(self, chat_id, password: str) -> Tuple[bool, str]:
        p = self._pending.get(chat_id)
        if p is None:
            return False, MISSING_PW_MSG
        try:
            await p["client"].sign_in(password=password)
        except Exception as e:
            return False, str(e)[:150]
        return True, await self._finish(chat_id, with_first_name=False)

    # ───────────────────────────── داخلی ─────────────────────────────
    async def _finish(self, chat_id, with_first_name: bool) -> str:
        """قطع اتصال + پاک‌کردن وضعیت + برچسب خوش‌آمد."""
        me = await self._pending[chat_id]["client"].get_me()
        await self._pending[chat_id]["client"].disconnect()
        self._pending.pop(chat_id, None)
        if me.username:
            return f"@{me.username}"
        return (me.first_name or "وصل شد") if with_first_name else "وصل شد"

    def pending(self, chat_id) -> bool:
        """آیا یک ورود نیمه‌تمام برای این چت در جریان است؟"""
        return chat_id in self._pending
