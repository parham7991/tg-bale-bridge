"""ویزارد نصب داخل بات تلگرام — همه‌چیز بدون دست زدن به کد یا شناسه عددی.

از همین چت بات:
  ۱) سلف تلگرام: api_id/api_hash + شماره + کد (و رمز دوم مرحله‌ای اگر باشد)
  ۲) سلف بله: شماره + کد پیامکی (نشست aiobale ساخته می‌شود)
  ۳) ربات بله: فقط توکن را paste کنید
  ۴) جفت کانال‌ها: یک پیام از کانال تلگرام فوروارد کنید یا @بدهید؛ همین‌طور بله؛
     بعد جهت را با دکمه انتخاب کنید — سپس دسترسی واقعی هر حساب تست و گزارش می‌شود.

اولین کسی که به بات /start بدهد ادمین می‌شود (بدون هیچ شناسه عددی در .env).
پایان نصب → برنامه خودش ری‌استارت می‌شود و پل کامل بالا می‌آید.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path

from .bot_api import BotAPI, BotAPIError

log = logging.getLogger("wizard")

ROOT = Path(__file__).resolve().parents[1]


def _tg_username(ref: str) -> str:
    ref = (ref or "").strip()
    m = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]{3,})", ref)
    return m.group(1) if m else ref.lstrip("@")


async def probe_tg_access(tg_client, chat_id) -> tuple[bool, str]:
    """آیا حساب تلگرام به کانال دسترسی دارد؟ (خواندن آخرین پیام)"""
    try:
        try:
            msgs = await tg_client.get_messages(int(chat_id), limit=1)
        except TypeError:
            msgs = await tg_client.get_messages(int(chat_id), ids=1)
        return True, "✔ دسترسی دارد" if msgs is not None else "✔"
    except Exception as e:
        return False, f"✘ {str(e)[:80]}"


async def probe_bale_access(bale_api, chat_id) -> tuple[bool, str]:
    """از موتور gateway بله — همان منطق، یک‌جا نگهداری می‌شود."""
    from .bale import BaleBotGateway

    return await BaleBotGateway.probe(bale_api, int(chat_id))


class Wizard:
    """مکالمهٔ نصب — روی بات تلگرام، با دکمه‌های شیشه‌ای."""

    def __init__(self, api, db, cfg, store, admin=None) -> None:
        self.api = api          # BotAPI بات مدیریت تلگرام
        self.db = db
        self.cfg = cfg
        self.store = store
        self.admin = admin
        self._st: dict = {}     # chat_id → {"state": str, "data": dict}

    # ------------------------------------------------------------ کیبورد
    def _menu_kb(self) -> dict:
        tg_ok = self.store.has_tg(self.cfg)
        rows = [
            [
                {"text": ("📱 سلف تلگرام ") + ("✅" if tg_ok else "○"),
                 "callback_data": "wiz:tg"},
                {"text": ("🟡 سلف بله ") + ("✅" if self.store.bale_self() else "○"),
                 "callback_data": "wiz:bale"},
            ],
            [
                {"text": ("🤖 ربات بله ") + ("✅" if self.store.bale_bot() else "○"),
                 "callback_data": "wiz:bbot"},
                {"text": "🔗 جفت کانال‌ها", "callback_data": "wiz:pair"},
            ],
            [
                {"text": "📊 وضعیت نصب", "callback_data": "wiz:status"},
                {"text": "🛡 ادمین‌کردن ربات", "callback_data": "wiz:promote"},
                {"text": "🌐 داشبورد", "callback_data": "wiz:dash"},
            ],
            [
                {"text": "✅ اتمام و راه‌اندازی", "callback_data": "wiz:done"},
            ],
        ]
        return {"inline_keyboard": rows}

    _DIR_KB = {"inline_keyboard": [[
        {"text": "↔ دوطرفه", "callback_data": "wiz:dir:both"},
        {"text": "تلگرام→بله", "callback_data": "wiz:dir:tg2bale"},
        {"text": "بله→تلگرام", "callback_data": "wiz:dir:bale2tg"},
    ]]}

    # ------------------------------------------------------------ چرخهٔ کار
    def is_active(self, chat_id) -> bool:
        return int(chat_id) in self._st

    def _state(self, chat_id) -> dict:
        return self._st.setdefault(int(chat_id), {"state": None, "data": {}})

    async def _send(self, chat_id, text: str, kb: dict | None = None) -> None:
        try:
            await self.api.send_message(int(chat_id), text, reply_markup=kb)
        except BotAPIError as e:
            log.error("ارسال پیام ویزارد ناموفق: %s", e)

    async def _answer(self, cb_id: str, text: str = "") -> None:
        try:
            await self.api.call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})
        except Exception:
            pass

    async def open(self, chat_id, user_id) -> None:
        self._state(chat_id)["state"] = "menu"
        await self._send(chat_id, self._menu_text(), self._menu_kb())

    def _menu_text(self) -> str:
        s = self.store
        st = self.cfg
        bale_bot = s.bale_bot()
        bb_name = ("@" + bale_bot["me"].get("username")
                   if bale_bot and bale_bot.get("me", {}).get("username")
                   else None)
        lines = [
            "🧙‍♂️ *ویزارد نصب پل تلگرام ⇄ بله*",
            "",
            f"{'✅' if s.has_tg(st) else '○'} سلف تلگرام"
            f" — {('شماره ' + s.tg_self().get('phone', '?')) if s.tg_self() else 'تنظیم نشده'}",
            f"{'✅' if s.bale_self() else '○'} سلف بله"
            f" — {('شماره ' + s.bale_self().get('phone', '?')) if s.bale_self() else 'تنظیم نشده'}",
            f"{'✅' if bale_bot else '○'} ربات بله — {bb_name or 'تنظیم نشده'}",
            f"▫️ جفت‌های کانال: {len(self.db.list_pairs())}",
            "",
            "از دکمه‌ها استفاده کنید. برای جفت‌کردن، یک پیام از هر کانال",
            "را در همین چت **فوروارد** کنید یا @آیدی‌اش را بفرستید.",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------ ورودی متن
    async def handle_text(self, chat_id, user_id, text: str, msg: dict | None = None) -> None:
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
            await self._send(chat_id, "✅ سلف تلگرام وصل شد! (رمز دوم پذیرفته شد)", self._menu_kb())
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
            token = text.split()[-1] if ":" in text else text
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
            await self._send(chat_id,
                             "📱 نصب سلف تلگرام — سه مرحله:\n"
                             "۱) api_id را بفرستید (از my.telegram.org → API development tools):\n"
                             "💡 اگر از قبل در .env گذاشته‌اید، همان را دوباره بفرستید.")
        elif action == "bale":
            st["state"], st["data"] = "bale_phone", {}
            await self._answer(cb_id)
            await self._send(chat_id,
                             "🟡 نصب سلف بله:\nشماره تلفن بله را بفرستید (مثلاً +98912...)")
        elif action == "bbot":
            st["state"], st["data"] = "bbot_token", {}
            await self._answer(cb_id)
            await self._send(chat_id,
                             "🤖 توکن ربات بله را بفرستید (از @botfather بله — عدد:AA...)")
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

    # ------------------------------------------------------------ جفت کانال
    async def _pair_begin(self, chat_id, msg) -> None:
        st = self._state(chat_id)
        st["data"] = {}
        st["state"] = "pair_tg"
        hint = ("🔗 جفت‌کردن کانال‌ها — مرحله ۱ از ۲:\n"
                "یک پیام از **کانال تلگرام** را فوروارد کنید، یا @آیدی/لینک/شناسه‌اش را بفرستید.")
        await self._send(chat_id, hint)

    async def _pair_tg_resolve(self, chat_id, text, msg) -> None:
        st = self._state(chat_id)
        fwd = (msg or {}).get("forward_from_chat") or {}
        origin = ((msg or {}).get("forward_origin") or {})
        if not fwd and origin.get("type") == "chat":
            fwd = {"id": origin.get("chat", {}).get("id"),
                   "title": origin.get("chat", {}).get("title"),
                   "username": origin.get("chat", {}).get("username")}
        if fwd and fwd.get("id"):
            info = {"id": int(fwd["id"]), "title": fwd.get("title") or "",
                    "username": (fwd.get("username") or "")}
        else:
            client = await self._tg_client()
            if client is None:
                await self._send(chat_id, "ابتدا سلف تلگرام را نصب کنید (دکمه 📱) تا بتوانم"
                                          " کانال را پیدا کنم.")
                return
            try:
                entity = await client.get_entity(_tg_username(text) if "@" in text or "t.me" in text
                                                 else (int(text) if text.lstrip("-").isdigit()
                                                       else text))
                info = {"id": int(entity.id),
                        "title": getattr(entity, "title", None) or "",
                        "username": getattr(entity, "username", None) or ""}
            except Exception as e:
                await self._send(chat_id, f"❌ کانال پیدا نشد: {str(e)[:120]}\n"
                                          "دوباره فوروارد کنید یا @آیدی بدهید:")
                return
        st["data"]["tg"] = info
        st["state"] = "pair_bale"
        await self._send(chat_id,
                         f"✅ کانال تلگرام: {info['title'] or info['username'] or info['id']}\n\n"
                         "مرحله ۲ از ۲ — کانال بله: @آیدی یا شناسه عددی‌اش را بفرستید"
                         " (یا یک پیامش را به بات بله فوروارد… فعلاً @آیدی).")

    async def _pair_bale_resolve(self, chat_id, text, msg) -> None:
        st = self._state(chat_id)
        ref = text.strip()
        bale_api = await self._bale_api_for_setup()
        if bale_api is None:
            await self._send(chat_id, "ابتدا سلف بله یا ربات بله را نصب کنید (دکمه‌های 🟡/🤖).")
            return
        try:
            info = await bale_api.get_chat(ref)
        except Exception as e:
            await self._send(chat_id, f"❌ کانال بله پیدا نشد: {str(e)[:120]}\n@آیدی درست بدهید:")
            return
        st["data"]["bale"] = info
        st["state"] = "pair_dir"
        tg_info = st["data"].get("tg") or {}
        await self._send(
            chat_id,
            "✅ کانال بله: {}\n\nجهت همگام‌سازی را انتخاب کنید:\n"
            "▫️ {}: {} ⇄ {}\n(بعدش دسترسی واقعی همهٔ حساب‌ها تست می‌شود)".format(
                info.get("title") or info.get("username") or info.get("id"),
                "جهت", tg_info.get("title") or tg_info.get("username") or tg_info.get("id"),
                info.get("title") or info.get("username") or info.get("id")),
            self._DIR_KB)

    async def _pair_finish(self, chat_id, mode: str) -> None:
        st = self._state(chat_id)
        data = st.get("data") or {}
        tg_info, bale_info = data.get("tg") or {}, data.get("bale") or {}
        if not tg_info or not bale_info:
            await self._send(chat_id, "ابتدا هر دو کانال را انتخاب کنید (دکمه 🔗).")
            st["state"] = "menu"
            return
        pair_id = self.db.add_pair(
            tg_info["id"], tg_info.get("title") or "", tg_info.get("username") or "",
            bale_info["id"], bale_info.get("title") or "", bale_info.get("username") or "",
            mode)
        st["state"] = "menu"
        await self._send(chat_id, f"✅ جفت #{pair_id} ثبت شد — در حال تست دسترسی‌ها…")
        report = await self._access_report(pair_id)
        await self._send(chat_id, report, self._menu_kb())

    # ------------------------------------------------------------ داشبورد وب
    async def _dash_info(self, chat_id) -> None:
        from .dashboard import Dashboard

        if not getattr(self.cfg, "DASH_ENABLED", True):
            await self._send(chat_id, "داشبورد خاموش است (DASH_ENABLED=0).")
            return
        user, password, created = Dashboard.ensure_credentials(self.store)
        host = getattr(self.cfg, "DASH_HOST", "0.0.0.0")
        port = getattr(self.cfg, "DASH_PORT", 8080)
        addr = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://<IP-سرور>:{port}"
        text = f"🌐 داشبورد وب:\n{addr}\n▫️ یوزرنیم: {user}\n"
        text += (f"▫️ رمز اولیه: {password}\n⚠️ فقط همین‌جا نشان داده می‌شود — عوضش کنید!\n"
                 if created else
                 "▫️ رمز: ست شده است (با /passwd عوض کنید یا از خود داشبورد).\n")
        await self._send(chat_id, text, self._menu_kb())

    # ------------------------------------------------------------ ادمین‌کردن ربات
    async def _promote_begin(self, chat_id) -> None:
        """سلف بله (که ادمین کانال است) ربات بله را اضافه و ادمین می‌کند."""
        if not self.store.bale_self():
            await self._send(chat_id,
                             "برای ادمین‌کردن ربات، اول سلف بله را نصب کنید (دکمه 🟡) —\n"
                             "سلف باید در کانال ادمین باشد.")
            return
        bb = self.store.bale_bot()
        if not bb:
            await self._send(chat_id, "اول ربات بله را ثبت کنید (دکمه 🤖).")
            return
        pairs = self.db.list_pairs()
        if not pairs:
            await self._send(chat_id, "اول جفت کانال بسازید (دکمه 🔗).")
            return
        await self._send(chat_id, "⏳ در حال افزودن ربات بله به کانال‌ها و ادمین‌کردن…")
        api = await self._bale_user_api()
        if api is None:
            await self._send(chat_id, "❌ اتصال سلف بله برقرار نشد — دوباره تلاش کنید.")
            return
        bot_api = self._bale_bot_api()
        me = bb.get("me") or {}
        bot_ref = me.get("username") or me.get("id")
        lines = ["🛡 نتیجهٔ ادمین‌کردن ربات بله:"]
        try:
            for p in pairs:
                label = p["bale_label"] or p["bale_chat_id"]
                try:
                    await api.add_admin(p["bale_chat_id"], bot_ref)
                    note = "✔ اضافه و ادمین شد"
                    if bot_api is not None:
                        ok, pnote = await probe_bale_access(bot_api, p["bale_chat_id"])
                        note += " — تست ارسال: " + ("✔" if ok else f"✘ {pnote}")
                except Exception as e:
                    note = f"✘ {str(e)[:120]}"
                lines.append(f"  ▫️ {label}: {note}")
        finally:
            try:
                await api.close()
            except Exception:
                pass
        await self._send(chat_id, "\n".join(lines), self._menu_kb())

    # ------------------------------------------------------------ گزارش دسترسی
    async def _access_report(self, pair_id: int | None = None) -> str:
        pairs = self.db.list_pairs()
        if pair_id is not None:
            pairs = [p for p in pairs if p["id"] == pair_id]
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        tg_client = await self._tg_client()
        bale_user = await self._bale_user_api()
        bale_bot = self._bale_bot_api()
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            if tg_client is not None:
                ok, note = await probe_tg_access(tg_client, p["tg_chat_id"])
                lines.append(f"  ▫️ سلف تلگرام → کانال تلگرام: {note}")
            else:
                lines.append("  ▫️ سلف تلگرام: — تنظیم نشده")
            if bale_user is not None:
                ok, note = await probe_bale_access(bale_user, p["bale_chat_id"])
                lines.append(f"  ▫️ سلف بله → کانال بله: {note}")
            else:
                lines.append("  ▫️ سلف بله: — تنظیم نشده")
            if bale_bot is not None:
                ok, note = await probe_bale_access(bale_bot, p["bale_chat_id"])
                lines.append(f"  ▫️ ربات بله → کانال بله: {note} (در حالت سلف لازم نیست)")
        return "\n".join(lines)

    async def access_report(self, chat_id) -> None:
        await self._send(chat_id, "⏳ در حال تست واقعی دسترسی‌ها…")
        await self._send(chat_id, await self._access_report())

    # ------------------------------------------------------------ تلگرام: لاگین
    async def _tg_client(self):
        """کلاینت سلف تلگرام اگر آماده باشد (برای resolve و probe)."""
        if not self.store.has_tg(self.cfg):
            return None
        api = self.store.tg_api() or {}
        api_id = int(getattr(self.cfg, "TG_API_ID", 0) or 0) or int(api.get("api_id", 0))
        api_hash = getattr(self.cfg, "TG_API_HASH", "") or api.get("api_hash", "")
        from telethon import TelegramClient

        client = TelegramClient(str(self.cfg.SESSION_PATH), api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            return None
        return client

    async def _tg_request_code(self, chat_id, phone: str) -> tuple[bool, str]:
        data = self._state(chat_id)["data"]
        api = self.store.tg_api() or {}
        api_id = int(data.get("api_id") or getattr(self.cfg, "TG_API_ID", 0) or 0
                     or api.get("api_id", 0))
        api_hash = (data.get("api_hash") or getattr(self.cfg, "TG_API_HASH", "")
                    or api.get("api_hash", ""))
        if not api_id or not api_hash:
            return False, "api_id/api_hash نامعتبر"
        from telethon import TelegramClient

        self.cfg.TG_API_ID, self.cfg.TG_API_HASH = api_id, api_hash
        client = TelegramClient(str(self.cfg.SESSION_PATH), api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            sent = await client.send_code_request(phone)
            data["phone_code_hash"] = getattr(sent, "phone_code_hash", None)
        self._st[chat_id]["tg_client"] = client  # نگه می‌داریم برای sign_in
        return True, "کد ارسال شد"

    async def _tg_sign_in(self, chat_id, code: str) -> tuple:
        client = self._st[chat_id].get("tg_client")
        data = self._state(chat_id)["data"]
        if client is None:
            return False, "نشست از دست رفت — از اول (دکمه 📱)"
        from telethon.errors import SessionPasswordNeededError

        try:
            await client.sign_in(phone=data.get("phone"), code=code,
                                 phone_code_hash=data.get("phone_code_hash"))
        except SessionPasswordNeededError:
            return "need_password", ""
        except Exception as e:
            return False, str(e)[:150]
        me = await client.get_me()
        await client.disconnect()
        self._st[chat_id]["tg_client"] = None
        return True, f"@{me.username}" if me.username else (me.first_name or "وصل شد")

    async def _tg_password(self, chat_id, password: str) -> tuple[bool, str]:
        client = self._st[chat_id].get("tg_client")
        if client is None:
            return False, "نشست از دست رفت"
        try:
            await client.sign_in(password=password)
        except Exception as e:
            return False, str(e)[:150]
        me = await client.get_me()
        await client.disconnect()
        self._st[chat_id]["tg_client"] = None
        return True, f"@{me.username}" if me.username else "وصل شد"

    # ------------------------------------------------------------ بله: لاگین سلف
    async def _bale_request_code(self, phone: str) -> tuple[bool, str]:
        from aiobale import Client
        from aiobale.enums import AuthErrors

        sess = Path(str(self.cfg.BALE_SESSION))
        sess = sess if sess.suffix == ".bale" else sess.with_suffix(".bale")
        client = Client(session_file=str(sess))
        resp = await asyncio.wait_for(client.start_phone_auth(int(phone)), timeout=45)
        if isinstance(resp, AuthErrors):
            return False, f"خطای بله: {resp.name}"
        txn = getattr(resp, "transaction_hash", None)
        if not txn:
            return False, "پاسخ نامعتبر سرور"
        self._txns["hash"] = txn
        return True, "کد ارسال شد"

    async def _bale_validate(self, chat_id, code: str) -> tuple[bool, str]:
        from aiobale import Client
        from aiobale.enums import AuthErrors

        txn = self._txns.get("hash")
        if not txn:
            return False, "اول شماره را بفرستید"
        sess = Path(str(self.cfg.BALE_SESSION))
        sess = sess if sess.suffix == ".bale" else sess.with_suffix(".bale")
        sess.parent.mkdir(parents=True, exist_ok=True)
        client = Client(session_file=str(sess))
        resp = await asyncio.wait_for(client.validate_code(code, txn), timeout=45)
        if isinstance(resp, AuthErrors):
            return False, f"خطای بله: {resp.name}"
        self._txns.pop("hash", None)
        return True, "نشست ذخیره شد"

    # ------------------------------------------------------------ بله: ربات
    def _bale_bot_api(self) -> BotAPI | None:
        bb = self.store.bale_bot()
        if not bb:
            return None
        return BotAPI(bb["token"], getattr(self.cfg, "BALE_API_BASE",
                                           "https://tapi.bale.ai"))

    async def _bale_user_api(self):
        if not self.store.bale_self():
            return None
        from .bale import BaleUserAPI

        api = BaleUserAPI(session_file=self.cfg.BALE_SESSION, db=self.db)
        try:
            await api.start()
        except Exception as e:
            log.warning("اتصال سلف بله برای resolve ناموفق: %s", e)
            return None
        return api

    async def _bale_api_for_setup(self):
        api = await self._bale_user_api()
        if api is not None:
            return api
        return self._bale_bot_api()

    async def _check_bale_bot(self, token: str) -> tuple[bool, dict | str]:
        try:
            api = BotAPI(token, getattr(self.cfg, "BALE_API_BASE", "https://tapi.bale.ai"))
            me = await asyncio.wait_for(api.get_me(), timeout=20)
            await api.close()
            return True, me
        except Exception as e:
            return False, f"توکن نامعتبر: {str(e)[:100]}"

    # ------------------------------------------------------------ پایان
    async def _finish(self, chat_id) -> None:
        self.store.set("install_done_at", int(time.time()))
        if not self.store.installed(self.cfg):
            missing = []
            if not self.store.has_tg(self.cfg):
                missing.append("سلف تلگرام (دکمه 📱)")
            if not self.store.has_bale(self.cfg):
                missing.append("سمت بله (دکمه 🟡 یا 🤖)")
            await self._send(chat_id,
                             "هنوز کامل نشده:\n" + "\n".join(f"▫️ {m}" for m in missing)
                             + "\n\nیا اگر همه‌چیز را در .env دارید، فقط ری‌استارت کنید.",
                             self._menu_kb())
            return
        await self._send(chat_id,
                         "🎉 نصب کامل شد! برنامه در حال ری‌استارت برای بالا آمدن پل…\n"
                         "بعد از چند ثانیه /status بزنید.")
        asyncio.create_task(self._do_restart())

    @staticmethod
    async def _do_restart() -> None:
        await asyncio.sleep(2)
        log.warning("ری‌استارت خودکار بعد از نصب…")
        os.execv(sys.executable, [sys.executable, str(ROOT / "main.py")])
