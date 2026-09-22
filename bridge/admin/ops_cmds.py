"""OpsCommandsEngine — عملیات واقعی روی کانال‌ها: access (پروب) / promote (ادمین‌کردن)."""
from __future__ import annotations

import logging

logger = logging.getLogger("bridge.admin.ops")


class OpsCommandsEngine:
    """تست دسترسی هر حساب به کانال‌ها + ادمین‌کردن ربات بله توسط سلف."""

    def __init__(self, adm) -> None:
        self.adm = adm                  # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند

    @property
    def db(self):
        return self.adm.db

    @property
    def bale(self):
        return self.adm.bale

    @property
    def tg(self):
        return self.adm.tg

    async def access(self, platform, args, msg):
        """تست واقعی دسترسی هر حساب به کانال‌های هر جفت (ارسال/خواندن آزمایشی)."""
        from ..tguser import TgSelfGateway
        from .probes import probe_bale_access

        pairs = self.db.list_pairs()
        if not pairs:
            return "هنوز جفتی ثبت نشده — /add"
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            try:
                ok, note = await TgSelfGateway.probe(self.tg, p["tg_chat_id"])
            except Exception as e:
                note = f"✘ {str(e)[:60]}"
            lines.append(f"  ▫️ سلف تلگرام → {p['tg_label'] or p['tg_chat_id']}: {note}")
            try:
                ok, note = await probe_bale_access(self.bale, p["bale_chat_id"])
            except Exception as e:
                note = f"✘ {str(e)[:60]}"
            lines.append(f"  ▫️ سمت بله → {p['bale_label'] or p['bale_chat_id']}: {note}")
        return "\n".join(lines)

    async def promote(self, platform, args, msg):
        """سلف بله (ادمین کانال) ربات بله را به کانال‌ها اضافه و ادمین می‌کند."""
        from ..bale import BaleUserAPI

        if not isinstance(self.bale, BaleUserAPI):
            return ("🛡 این کار با سلف بله انجام می‌شود — در حالت ربات ممکن نیست.\n"
                    "BALE_MODE=user کنید (یا از ویزارد تلگرام: 🛡 ادمین‌کردن ربات).")
        args = [a for a in (args or []) if a]
        pairs = self.db.list_pairs()
        if args and args[0].isdigit():
            pid = int(args[0])
            pairs = [p for p in pairs if p["id"] == pid] or pairs
            bot_ref = args[1] if len(args) > 1 else None
        else:
            bot_ref = args[0] if args else None
        if not pairs:
            return "هنوز جفتی ثبت نشده — /add"
        if not bot_ref:
            return ("یوزرنیم ربات بله را بدهید: /promote @my_bale_bot\n"
                    "(یا از ویزارد بات تلگرام: 🛡 ادمین‌کردن ربات)")
        lines = ["🛡 نتیجهٔ ادمین‌کردن:"]
        for p in pairs:
            label = p["bale_label"] or p["bale_chat_id"]
            try:
                await self.bale.add_admin(p["bale_chat_id"], bot_ref)
                lines.append(f"  ▫️ {label}: ✔ اضافه و ادمین شد")
            except Exception as e:
                lines.append(f"  ▫️ {label}: ✘ {str(e)[:100]}")
        return "\n".join(lines)
