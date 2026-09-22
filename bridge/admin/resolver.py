"""ResolverEngine — شناسایی کانال‌ها و استخراج شناسه از فوروارد.

resolve تلگرام (با پیام خطای فارسی راهنما) و توضیح فورواردی برای هر سه شکل:
دیکت.Bot-API (بله/بات تلگرام) و آبجکت Telethon (سلف تلگرام).
"""
from __future__ import annotations

import logging
import re

from telethon import utils as tg_utils

logger = logging.getLogger("bridge.admin.resolver")


class ResolverEngine:
    """تبدیل ارجاع کاربر به شناسه/برچسب — فقط سمت تلگرام؛ بله از دروازهٔ بله."""

    def __init__(self, adm) -> None:
        self.adm = adm           # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند

    @property
    def tg(self):
        return self.adm.tg

    async def resolve_tg(self, ref: str):
        ref = ref.strip()
        try:
            if re.fullmatch(r"-?\d+", ref):
                ent = await self.tg.get_entity(int(ref))
            else:
                ent = await self.tg.get_entity(ref)
        except Exception as e:
            raise ValueError(
                f"کانال تلگرام «{ref}» پیدا نشد ({e}). حساب باید عضو آن کانال باشد؛ "
                "شناسه عددی را با /id بگیرید."
            ) from e
        marked = tg_utils.get_peer_id(ent)
        label = getattr(ent, "title", None) or " ".join(
            x for x in [getattr(ent, "first_name", ""), getattr(ent, "last_name", "")] if x
        ) or ""
        username = getattr(ent, "username", "") or ""
        return int(marked), label, username

    async def describe_forward(self, platform, msg) -> str | None:
        if not msg:
            return None
        try:
            if platform in ("bale", "tgbot"):
                chat = msg.get("forward_from_chat")
                user = msg.get("forward_from")
                origin = msg.get("forward_origin") or {}
                if not chat and origin.get("chat"):
                    chat = origin.get("chat")
                if not user and origin.get("sender_user"):
                    user = origin.get("sender_user")
                if not chat and not user and origin.get("sender_user_name"):
                    return f"ℹ️ فرستنده: {origin['sender_user_name']}"
                if chat:
                    uname = f"@{chat['username']}" if chat.get("username") else "—"
                    return (f"🆔 شناسه کانال مبدأ:\n"
                            f"▫️ نام: {chat.get('title') or uname}\n"
                            f"▫️ آیدی عددی: {chat['id']}\n"
                            f"▫️ یوزرنیم: {uname}\n\n"
                            f"مثال: /add <کانال_تلگرام> {chat['id']}")
                if user:
                    uname = f"@{user['username']}" if user.get("username") else "—"
                    return (f"🆔 شناسه کاربر مبدأ:\n▫️ آیدی عددی: {user['id']}\n"
                            f"▫️ یوزرنیم: {uname}")
                return None
            # تلگرام (سلف)
            fwd = getattr(msg, "forward", None)
            if not fwd:
                return None
            from_id = getattr(fwd, "from_id", None)
            if from_id is None:
                return f"ℹ️ فرستنده: {getattr(fwd, 'from_name', 'ناشناس')}"
            marked = tg_utils.get_peer_id(from_id)
            uname = "—"
            try:
                ent = await self.tg.get_entity(from_id)
                if getattr(ent, "username", None):
                    uname = f"@{ent.username}"
            except Exception:
                ent = None
            title = getattr(ent, "title", None) or getattr(fwd, "from_name", None) or uname
            return (f"🆔 شناسه چت مبدأ تلگرام:\n"
                    f"▫️ نام: {title}\n"
                    f"▫️ آیدی عددی (با -100): {marked}\n"
                    f"▫️ یوزرنیم: {uname}\n\n"
                    f"مثال: /add {marked} <کانال_بله>")
        except Exception:
            logger.exception("describe_forward failed")
            return None
