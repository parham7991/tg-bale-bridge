"""PairingEngine — جفت‌کردن کانال‌ها: دو مرحله resolve + انتخاب جهت + ثبت.

مرحله ۱: کانال تلگرام (فوروارد یا @آیدی با کمک سلف) — مرحله ۲: کانال بله
(با سلف یا ربات) — پایان: انتخاب جهت و ثبت در دیتابیس + گزارش دسترسی.
"""
from __future__ import annotations

import logging
from typing import Any

from .types_map import DIR_KB, forward_chat_info

logger = logging.getLogger("bridge.wizard.pairing")


class PairingEngine:
    """جریان جفت‌کردن — همهٔ I/O از طریق نما (پچ‌پذیر در تست‌ها)."""

    def __init__(self, wiz: Any, db: Any) -> None:
        self.wiz = wiz
        self.db = db

    # ───────────────────────────── مرحله ۱ ─────────────────────────────
    async def begin(self, chat_id, msg) -> None:
        st = self.wiz._state(chat_id)
        st["data"] = {}
        st["state"] = "pair_tg"
        hint = ("🔗 جفت‌کردن کانال‌ها — مرحله ۱ از ۲:\n"
                "یک پیام از **کانال تلگرام** را فوروارد کنید، یا @آیدی/لینک/شناسه‌اش را بفرستید.")
        await self.wiz._send(chat_id, hint)

    async def tg_resolve(self, chat_id, text, msg) -> None:
        from ..tguser import TgSelfGateway

        st = self.wiz._state(chat_id)
        info = forward_chat_info(msg)
        if info is None:
            client = await self.wiz._tg_client()
            if client is None:
                await self.wiz._send(chat_id, "ابتدا سلف تلگرام را نصب کنید (دکمه 📱) تا بتوانم"
                                              " کانال را پیدا کنم.")
                return
            try:
                ref = TgSelfGateway.normalize_username(text) \
                    if "@" in text or "t.me" in text \
                    else (int(text) if text.lstrip("-").isdigit() else text)
                entity = await client.get_entity(ref)
                info = {"id": int(entity.id),
                        "title": getattr(entity, "title", None) or "",
                        "username": getattr(entity, "username", None) or ""}
            except Exception as e:
                await self.wiz._send(chat_id, f"❌ کانال پیدا نشد: {str(e)[:120]}\n"
                                              "دوباره فوروارد کنید یا @آیدی بدهید:")
                return
        st["data"]["tg"] = info
        st["state"] = "pair_bale"
        label = info["title"] or info["username"] or info["id"]
        await self.wiz._send(
            chat_id,
            f"✅ کانال تلگرام: {label}\n\n"
            "مرحله ۲ از ۲ — کانال بله: @آیدی یا شناسه عددی‌اش را بفرستید"
            " (یا یک پیامش را به بات بله فوروارد… فعلاً @آیدی).")

    # ───────────────────────────── مرحله ۲ ─────────────────────────────
    async def bale_resolve(self, chat_id, text, msg) -> None:
        st = self.wiz._state(chat_id)
        ref = text.strip()
        bale_api = await self.wiz._bale_api_for_setup()
        if bale_api is None:
            await self.wiz._send(chat_id, "ابتدا سلف بله یا ربات بله را نصب کنید (دکمه‌های 🟡/🤖).")
            return
        try:
            info = await bale_api.get_chat(ref)
        except Exception as e:
            await self.wiz._send(
            chat_id, f"❌ کانال بله پیدا نشد: {str(e)[:120]}\n@آیدی درست بدهید:")
            return
        st["data"]["bale"] = info
        st["state"] = "pair_dir"
        tg_info = st["data"].get("tg") or {}
        await self.wiz._send(
            chat_id,
            "✅ کانال بله: {}\n\nجهت همگام‌سازی را انتخاب کنید:\n"
            "▫️ {}: {} ⇄ {}\n(بعدش دسترسی واقعی همهٔ حساب‌ها تست می‌شود)".format(
                info.get("title") or info.get("username") or info.get("id"),
                "جهت", tg_info.get("title") or tg_info.get("username") or tg_info.get("id"),
                info.get("title") or info.get("username") or info.get("id")),
            DIR_KB)

    # ───────────────────────────── ثبت ─────────────────────────────
    async def finish(self, chat_id, mode: str) -> None:
        st = self.wiz._state(chat_id)
        data = st.get("data") or {}
        tg_info, bale_info = data.get("tg") or {}, data.get("bale") or {}
        if not tg_info or not bale_info:
            await self.wiz._send(chat_id, "ابتدا هر دو کانال را انتخاب کنید (دکمه 🔗).")
            st["state"] = "menu"
            return
        pair_id = self.db.add_pair(
            tg_info["id"], tg_info.get("title") or "", tg_info.get("username") or "",
            bale_info["id"], bale_info.get("title") or "", bale_info.get("username") or "",
            mode)
        st["state"] = "menu"
        await self.wiz._send(chat_id, f"✅ جفت #{pair_id} ثبت شد — در حال تست دسترسی‌ها…")
        report = await self.wiz._access_report(pair_id)
        await self.wiz._send(chat_id, report, self.wiz._menu_kb())
