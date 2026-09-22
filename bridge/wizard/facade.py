"""Wizard — نمای سازگاری ویزارد نصب (ریشهٔ ترکیب بستهٔ wizard).

سطح عمومی دقیقاً مثل قبل: همان ``Wizard(api, db, cfg, store, admin=None)`` با
``open / is_active / handle_text / handle_callback`` و همهٔ متدهای داخلی —
اما داخل، هر بخش به موتور خودش تفویض می‌شود:

    types_map → ثابت‌ها/استخراج       · menu    → MenuEngine
    accounts  → AccountsEngine        · pairing → PairingEngine
    checks    → AccessReportEngine    · promote → PromoteEngine
    dashinfo  → DashInfoEngine        · finish  → FinishEngine
    probes    → توابع سازگاری         · login   → موتورهای ورود tguser/bale

ماشین حالت (FSM) همین‌جاست — تنها نقطه‌ای که «ترتیب سؤال‌ها» را می‌داند.
"""
from __future__ import annotations

import logging
from typing import Any

from ..bot_api import BotAPIError
from .accounts import AccountsEngine
from .checks import AccessReportEngine
from .dashinfo import DashInfoEngine
from .finish import FinishEngine
from .menu import MenuEngine
from .pairing import PairingEngine
from .promote import PromoteEngine
from .types_map import DIR_KB, PROMPT_BALE, PROMPT_BBOT, PROMPT_TG, extract_token

logger = logging.getLogger("wizard")


class Wizard:
    """مکالمهٔ نصب — روی بات تلگرام، با دکمه‌های شیشه‌ای."""

    def __init__(self, api, db, cfg, store, admin=None) -> None:
        self.api = api          # BotAPI بات مدیریت تلگرام
        self.db = db
        self.cfg = cfg
        self.store = store
        self.admin = admin
        self._st: dict = {}     # chat_id → {"state": str, "data": dict}
        # ── موتورها ──
        self.menu = MenuEngine(db, cfg, store)
        self.accounts = AccountsEngine(self, cfg, store)
        self.pairing = PairingEngine(self, db)
        self.reports = AccessReportEngine(self, db)
        self.promote_engine = PromoteEngine(self, db, store)
        self.dashinfo = DashInfoEngine(self, cfg, store)
        self.finish_engine = FinishEngine(self, store, cfg)
        # موتور ورود سلف بله (همان منطق login_bale.py — یک منبع)
        from ..bale import BaleLoginEngine

        self._bale_login = BaleLoginEngine(
            getattr(cfg, "BALE_SESSION", "data/session"),
            (getattr(cfg, "BALE_PHONE", "") or "").strip() or None,
        )
        # موتور ورود سلف تلگرام (دومرحله‌ای + رمز دوم — یک منبع)
        from ..tguser import TgLoginEngine

        self._tg_login = TgLoginEngine(cfg, store)

    # ------------------------------------------------------------ کیبورد و منو
    def _menu_kb(self) -> dict:
        return self.menu.kb()

    _DIR_KB = DIR_KB

    def _menu_text(self) -> str:
        return self.menu.text()

    # ------------------------------------------------------------ چرخهٔ کار
    def is_active(self, chat_id) -> bool:
        return int(chat_id) in self._st

    def _state(self, chat_id) -> dict:
        return self._st.setdefault(int(chat_id), {"state": None, "data": {}})

    async def _send(self, chat_id, text: str, kb: dict | None = None) -> None:
        try:
            await self.api.send_message(int(chat_id), text, reply_markup=kb)
        except BotAPIError as e:
            logger.error("ارسال پیام ویزارد ناموفق: %s", e)

    async def _answer(self, cb_id: str, text: str = "") -> None:
        try:
            await self.api.call("answerCallbackQuery",
                                {"callback_query_id": cb_id, "text": text})
        except Exception:
            pass

    async def open(self, chat_id, user_id) -> None:
        self._state(chat_id)["state"] = "menu"
        await self._send(chat_id, self._menu_text(), self._menu_kb())

    # ------------------------------------------------------------ ورودی متن (FSM)
    async def handle_text(self, chat_id, user_id, text: str,
                          msg: dict | None = None) -> None:
        st = self._state(chat_id)
        state, data = st["state"], st["data"]
        text = (text or "").strip()

        if state in (None, "menu"):
            # در منو: پیام فورواردی = شروع جفت‌کردن از همان فوروارد
            fwd = (msg or {}).get("forward_from_chat") or {}
            origin = (msg or {}).get("forward_origin") or {}
            if fwd or origin.get("type") == "chat":
                await self._pair_begin(chat_id, msg)
                await self._pair_tg_resolve(chat_id, text, msg)
                return
            await self.open(chat_id, user_id)
            return

        if state == "tg_api_id":
            if not text.isdigit():
                await self._send(chat_id, "❌ api_id باید عدد باشد — دوباره بفرستید:")
                return
            data["api_id"] = int(text)
            st["state"] = "tg_api_hash"
            await self._send(chat_id, "۲) حالا api_hash را بفرستید (۳۲ کاراکتر هگز):")
        elif state == "tg_api_hash":
            data["api_hash"] = text
            self.store.set_tg_api(data["api_id"], text)
            st["state"] = "tg_phone"
            await self._send(chat_id, "۳) شماره تلفن حساب تلگرام را بفرستید (مثلاً +98912...):")
        elif state == "tg_phone":
            try:
                await self._send(chat_id, "⏳ در حال اتصال به تلگرام و ارسال کد…")
                ok, info = await self._tg_request_code(chat_id, text)
            except Exception as e:
                ok, info = False, f"{type(e).__name__}: {str(e)[:150]}"
            if not ok:
                st["state"] = "tg_phone"
                await self._send(chat_id, f"❌ {info}\nشماره را دوباره بفرستید:")
                return
            data["phone"] = text
            st["state"] = "tg_code"
            await self._send(chat_id, "۴) کد ۵ رقمی که تلگرام فرستاد را بفرستید"
                                     " (اگر رمز دوم دارید بعدش می‌پرسم):")
        elif state == "tg_code":
            ok, info = await self._tg_sign_in(chat_id, text)
            if ok == "need_password":
                st["state"] = "tg_password"
                await self._send(chat_id, "🔐 رمز دوم (2FA) را بفرستید:")
                return
            if not ok:
                await self._send(chat_id, f"❌ {info}\nکد را دوباره بفرستید:")
                return
            self.store.set_tg_self(data.get("phone", ""))
            st["state"], data["tg_done"] = "menu", True
            await self._send(chat_id, f"✅ سلف تلگرام وصل شد! ({info})", self._menu_kb())
        elif state == "tg_password":
            ok, info = await self._tg_password(chat_id, text)
            if not ok:
                await self._send(chat_id, f"❌ {info}\nرمز را دوباره بفرستید:")
                return
            self.store.set_tg_self(data.get("phone", ""))
            st["state"] = "menu"
            await self._send(chat_id, "✅ سلف تلگرام وصل شد! (رمز دوم پذیرفته شد)",
                             self._menu_kb())
        elif state == "bale_phone":
            try:
                await self._send(chat_id, "⏳ در حال ارسال کد به بله…")
                ok, info = await self._bale_request_code(text)
            except Exception as e:
                ok, info = False, f"{type(e).__name__}: {str(e)[:150]}"
            if not ok:
                await self._send(chat_id, f"❌ {info}\nشماره را دوباره بفرستید:")
                return
            data["bale_phone"] = text
            st["state"] = "bale_code"
            await self._send(chat_id, "کد ۵ رقمی بله (پیامک یا داخل خود اپ) را بفرستید:")
        elif state == "bale_code":
            ok, info = await self._bale_validate(chat_id, text)
            if not ok:
                await self._send(chat_id, f"❌ {info}\nکد را دوباره بفرستید:")
                return
            self.store.set_bale_self(data.get("bale_phone", ""))
            st["state"] = "menu"
            await self._send(chat_id, "✅ سلف بله وصل شد! نشست ذخیره شد.", self._menu_kb())
        elif state == "bbot_token":
            token = extract_token(text)
            ok, info = await self._check_bale_bot(token)
            if not ok:
                await self._send(chat_id, f"❌ {info}\nتوکن را دوباره بفرستید:")
                return
            self.store.set_bale_bot(token, info)
            st["state"] = "menu"
            await self._send(chat_id,
                             f"✅ ربات بله ثبت شد: @{info.get('username')}", self._menu_kb())
        elif state == "pair_tg":
            await self._pair_tg_resolve(chat_id, text, msg)
        elif state == "pair_bale":
            await self._pair_bale_resolve(chat_id, text, msg)
        else:
            st["state"] = "menu"
            await self.open(chat_id, user_id)

    # ------------------------------------------------------------ دکمه‌ها
    async def handle_callback(self, cb: dict) -> None:
        cb_id = cb.get("id") or ""
        msg = cb.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        data = cb.get("data") or ""
        if not chat_id or not data.startswith("wiz:"):
            return
        action = data.split(":", 1)[1]
        st = self._state(chat_id)

        if action == "menu":
            st["state"] = "menu"
            await self._answer(cb_id)
            await self._send(chat_id, self._menu_text(), self._menu_kb())
        elif action == "tg":
            st["state"], st["data"] = "tg_api_id", {}
            await self._answer(cb_id)
            await self._send(chat_id, PROMPT_TG)
        elif action == "bale":
            st["state"], st["data"] = "bale_phone", {}
            await self._answer(cb_id)
            await self._send(chat_id, PROMPT_BALE)
        elif action == "bbot":
            st["state"], st["data"] = "bbot_token", {}
            await self._answer(cb_id)
            await self._send(chat_id, PROMPT_BBOT)
        elif action == "pair":
            await self._answer(cb_id)
            await self._pair_begin(chat_id, None)
        elif action == "dash":
            await self._answer(cb_id)
            await self._dash_info(chat_id)
        elif action == "promote":
            await self._answer(cb_id)
            await self._promote_begin(chat_id)
        elif action == "status":
            await self._answer(cb_id, "وضعیت به‌روز شد")
            await self._send(chat_id, self._menu_text(), self._menu_kb())
        elif action == "done":
            await self._answer(cb_id)
            await self._finish(chat_id)
        elif action.startswith("dir:"):
            await self._answer(cb_id)
            await self._pair_finish(chat_id, action.split(":", 1)[1])
        else:
            await self._answer(cb_id)

    # ------------------------------------------------------------ تفویض: جفت کانال
    async def _pair_begin(self, chat_id, msg) -> None:
        await self.pairing.begin(chat_id, msg)

    async def _pair_tg_resolve(self, chat_id, text, msg) -> None:
        await self.pairing.tg_resolve(chat_id, text, msg)

    async def _pair_bale_resolve(self, chat_id, text, msg) -> None:
        await self.pairing.bale_resolve(chat_id, text, msg)

    async def _pair_finish(self, chat_id, mode: str) -> None:
        await self.pairing.finish(chat_id, mode)

    # ------------------------------------------------------------ تفویض: نمایش‌ها
    async def _dash_info(self, chat_id) -> None:
        await self.dashinfo.info(chat_id)

    async def _promote_begin(self, chat_id) -> None:
        await self.promote_engine.begin(chat_id)

    async def _access_report(self, pair_id: int | None = None) -> str:
        return await self.reports.report(pair_id)

    async def access_report(self, chat_id) -> None:
        await self._send(chat_id, "⏳ در حال تست واقعی دسترسی‌ها…")
        await self._send(chat_id, await self._access_report())

    # ------------------------------------------------------------ تفویض: پایان
    async def _finish(self, chat_id) -> None:
        await self.finish_engine.finish(chat_id)

    @staticmethod
    async def _do_restart() -> None:
        await FinishEngine.do_restart()

    # ------------------------------------------------------------ تفویض: حساب‌ها
    def _bale_bot_api(self) -> Any:
        return self.accounts.bale_bot_api()

    async def _bale_user_api(self):
        return await self.accounts.bale_user_api()

    async def _bale_api_for_setup(self):
        return await self.accounts.api_for_setup()

    async def _check_bale_bot(self, token: str) -> tuple[bool, Any]:
        return await self.accounts.check_bale_bot(token)

    # ------------------------------------------------------------ تفویض: ورود تلگرام
    async def _tg_client(self):
        """از دروازهٔ سلف تلگرام — کلاینت آماده برای resolve و probe."""
        from ..tguser import TgSelfGateway

        return await TgSelfGateway.ready_client(self.cfg, self.store)

    async def _tg_request_code(self, chat_id, phone: str) -> tuple[bool, str]:
        """از موتور ورود سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
        data = self._state(chat_id)["data"]
        return await self._tg_login.request_code(
            chat_id, phone, api_id=data.get("api_id"), api_hash=data.get("api_hash"))

    async def _tg_sign_in(self, chat_id, code: str) -> tuple:
        """از موتور ورود سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
        return await self._tg_login.sign_in(chat_id, code)

    async def _tg_password(self, chat_id, password: str) -> tuple[bool, str]:
        """از موتور ورود سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
        return await self._tg_login.password(chat_id, password)

    # ------------------------------------------------------------ تفویض: ورود بله
    async def _bale_request_code(self, phone: str) -> tuple[bool, str]:
        """از موتور ورود بله — همان منطق، یک‌جا نگهداری می‌شود."""
        return await self._bale_login.request_code(phone)

    async def _bale_validate(self, chat_id, code: str) -> tuple[bool, str]:
        """از موتور ورود بله — همان منطق، یک‌جا نگهداری می‌شود."""
        return await self._bale_login.validate_code(code)
