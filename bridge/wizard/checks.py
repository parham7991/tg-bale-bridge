"""AccessReportEngine — تست واقعی دسترسی همهٔ حساب‌ها به کانال‌های هر جفت.

سلف تلگرام (خواندن آخرین پیام)، سلف بله و ربات بله (ارسال/حذف پیام آزمایشی).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bridge.wizard.checks")


class AccessReportEngine:
    """گزارش دسترسی — پروب‌ها از دروازه‌های هر سمت می‌آیند."""

    def __init__(self, wiz: Any, db: Any) -> None:
        self.wiz = wiz
        self.db = db

    async def report(self, pair_id: int | None = None) -> str:
        from ..bale import BaleBotGateway
        from ..tguser import TgSelfGateway

        pairs = self.db.list_pairs()
        if pair_id is not None:
            pairs = [p for p in pairs if p["id"] == pair_id]
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        tg_client = await self.wiz._tg_client()
        bale_user = await self.wiz._bale_user_api()
        bale_bot = self.wiz._bale_bot_api()
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            if tg_client is not None:
                ok, note = await TgSelfGateway.probe(tg_client, p["tg_chat_id"])
                lines.append(f"  ▫️ سلف تلگرام → کانال تلگرام: {note}")
            else:
                lines.append("  ▫️ سلف تلگرام: — تنظیم نشده")
            if bale_user is not None:
                ok, note = await BaleBotGateway.probe(bale_user, p["bale_chat_id"])
                lines.append(f"  ▫️ سلف بله → کانال بله: {note}")
            else:
                lines.append("  ▫️ سلف بله: — تنظیم نشده")
            if bale_bot is not None:
                ok, note = await BaleBotGateway.probe(bale_bot, p["bale_chat_id"])
                if ok:
                    lines.append(f"  ▫️ ربات بله → کانال بله: {note}")
                elif bale_user is not None:
                    lines.append(f"  ▫️ ربات بله → کانال بله: — لازم نیست "
                                 f"(حالت سلف: ارسال با سلف انجام می‌شود) [{note}]")
                else:
                    lines.append(f"  ▫️ ربات بله → کانال بله: {note}")
        return "\n".join(lines)
