"""PairsCommandsEngine — دستورات مدیریت جفت‌ها: add / remove / mode / list."""
from __future__ import annotations

import logging

from ..bale import BaleBotGateway
from .types_map import MODE_ALIASES, MODE_LABELS

logger = logging.getLogger("bridge.admin.pairs")


class PairsCommandsEngine:
    """CRUD جفت‌های کانال — resolve واقعی هر دو سمت در /add."""

    def __init__(self, adm, resolver) -> None:
        self.adm = adm           # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند
        self.resolver = resolver

    @property
    def db(self):
        return self.adm.db

    @property
    def tg(self):
        return self.adm.tg

    @property
    def bale(self):
        return self.adm.bale

    async def add(self, platform, args, msg):
        if len(args) < 2:
            return "فرمت: /add <کانال_تلگرام> <کانال_بله> [both|tg2bale|bale2tg]"
        tg_ref, bale_ref = args[0], args[1]
        mode = "both"
        if len(args) >= 3:
            mode = MODE_ALIASES.get(args[2].lower().replace("-", "_"))
            if not mode:
                return "حالت نامعتبر. یکی از: both ، tg2bale ، bale2tg"

        tg_id, tg_label, tg_username = await self.resolver.resolve_tg(tg_ref)
        bale_id, bale_label, bale_username = await self.resolve_bale(bale_ref)

        pair_id = self.db.add_pair(tg_id, tg_label, tg_username,
                                   bale_id, bale_label, bale_username, mode)
        return (f"✅ جفت #{pair_id} ثبت شد.\n"
                f"▫️ تلگرام: {tg_label or tg_username or tg_id}\n"
                f"▫️ بله: {bale_label or bale_username or bale_id}\n"
                f"▫️ جهت: {MODE_LABELS[mode]}\n\n"
                "دقت کنید: حساب تلگرام باید عضو کانال تلگرام باشد و ربات بله باید در کانال بله "
                "ادمین با دسترسی ارسال/ویرایش/حذف باشد.")

    def remove(self, platform, args, msg):
        if not args:
            return "فرمت: /remove <شناسه جفت>"
        ok = self.db.remove_pair(int(args[0]))
        return "✅ جفت حذف شد." if ok else "چنین جفتی پیدا نشد."

    def mode(self, platform, args, msg):
        if len(args) < 2:
            return "فرمت: /mode <شناسه جفت> <both|tg2bale|bale2tg>"
        mode = MODE_ALIASES.get(args[1].lower().replace("-", "_"))
        if not mode:
            return "حالت نامعتبر. یکی از: both ، tg2bale ، bale2tg"
        ok = self.db.set_mode(int(args[0]), mode)
        return f"✅ جهت جفت #{args[0]} → {MODE_LABELS[mode]}" if ok else "چنین جفتی پیدا نشد."

    def list(self, platform, args, msg):
        pairs = self.db.list_pairs()
        if not pairs:
            return "هنوز جفتی ثبت نشده. با /add شروع کنید."
        lines = ["📋 جفت‌های متصل:", ""]
        for p in pairs:
            lines.append(
                f"#{p['id']} | {MODE_LABELS.get(p['mode'], p['mode'])}\n"
                f"   تلگرام: {p['tg_label'] or p['tg_username'] or p['tg_chat_id']}\n"
                f"   بله: {p['bale_label'] or p['bale_username'] or p['bale_chat_id']}"
            )
        return "\n".join(lines)

    async def resolve_bale(self, ref: str):
        """از موتور gateway بله — همان منطق، یک‌جا نگهداری می‌شود."""
        return await BaleBotGateway(self.bale).resolve(ref)
