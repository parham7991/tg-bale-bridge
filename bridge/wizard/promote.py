"""PromoteEngine — سلف بله (ادمین کانال) ربات بله را به کانال‌ها اضافه و ادمین می‌کند."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bridge.wizard.promote")


class PromoteEngine:
    """ادمین‌کردن ربات بله روی همهٔ جفت‌ها + تست ارسال پس از هر کدام."""

    def __init__(self, wiz: Any, db: Any, store: Any) -> None:
        self.wiz = wiz
        self.db = db
        self.store = store

    async def begin(self, chat_id) -> None:
        from ..bale import BaleBotGateway

        if not self.store.bale_self():
            await self.wiz._send(chat_id,
                                 "برای ادمین‌کردن ربات، اول سلف بله را نصب کنید (دکمه 🟡) —\n"
                                 "سلف باید در کانال ادمین باشد.")
            return
        bb = self.store.bale_bot()
        if not bb:
            await self.wiz._send(chat_id, "اول ربات بله را ثبت کنید (دکمه 🤖).")
            return
        pairs = self.db.list_pairs()
        if not pairs:
            await self.wiz._send(chat_id, "اول جفت کانال بسازید (دکمه 🔗).")
            return
        await self.wiz._send(chat_id, "⏳ در حال افزودن ربات بله به کانال‌ها و ادمین‌کردن…")
        api = await self.wiz._bale_user_api()
        if api is None:
            await self.wiz._send(chat_id, "❌ اتصال سلف بله برقرار نشد — دوباره تلاش کنید.")
            return
        bot_api = self.wiz._bale_bot_api()
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
                        ok, pnote = await BaleBotGateway.probe(bot_api, p["bale_chat_id"])
                        note += " — تست ارسال: " + ("✔" if ok else f"✘ {pnote}")
                except Exception as e:
                    note = f"✘ {str(e)[:120]}"
                lines.append(f"  ▫️ {label}: {note}")
        finally:
            try:
                await api.close()
            except Exception:
                pass
        await self.wiz._send(chat_id, "\n".join(lines), self.wiz._menu_kb())
