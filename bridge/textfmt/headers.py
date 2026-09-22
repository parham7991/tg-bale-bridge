"""HeadersEngine — هدرهای «باز‌ارسال از» برای هر دو سمت.

تلگرام: از MessageFwdHeader (نام مستقیم، entity، یا نویسندهٔ پست).
بله: کلیدهای forward_from_chat / forward_from در دیکشنری Bot-API شکل.
"""
from __future__ import annotations

from .types_map import FORWARD_HEADER_TPL


class HeadersEngine:
    """ساخت هدر فوروارد — سمت تلگرام async است (entity lookup)."""

    @staticmethod
    async def tg_forward_header(msg, client) -> str:
        fwd = getattr(msg, "forward", None)
        if not fwd:
            return ""
        name = getattr(fwd, "from_name", None)
        if not name:
            from_id = getattr(fwd, "from_id", None)
            try:
                if from_id is not None:
                    ent = await client.get_entity(from_id)
                    name = getattr(ent, "title", None) or " ".join(
                        x for x in [getattr(ent, "first_name", ""),
                                    getattr(ent, "last_name", "")] if x
                    )
            except Exception:
                name = None
        if not name and getattr(fwd, "post_author", None):
            name = fwd.post_author
        return FORWARD_HEADER_TPL.format(name or "ناشناس")

    @staticmethod
    def bale_forward_header(m: dict) -> str:
        chat = m.get("forward_from_chat")
        if chat:
            name = chat.get("title") or ("@" + chat["username"]
                                         if chat.get("username") else None)
            return FORWARD_HEADER_TPL.format(name or "ناشناس")
        user = m.get("forward_from")
        if user:
            name = " ".join(
                x for x in [user.get("first_name") or "", user.get("last_name") or ""]
                if x
            ).strip()
            return FORWARD_HEADER_TPL.format(name or user.get("username") or "ناشناس")
        return ""


# توابع سطح ماژول — سطح عمومی همیشه‌سبز
async def tg_forward_header(msg, client) -> str:
    return await HeadersEngine.tg_forward_header(msg, client)


def bale_forward_header(m: dict) -> str:
    return HeadersEngine.bale_forward_header(m)
