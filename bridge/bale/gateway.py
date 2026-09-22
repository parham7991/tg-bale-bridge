"""BaleBotGateway — موتور «ربات بله» (Bot-API): resolve چت + پروب واقعی دسترسی.

این موتور منطقی است که قبلاً در admin._resolve_bale و wizard.probe_bale_access
پراکنده بود — حالا یک‌جا، بدون وابستگی به HTTP یا بات تلگرام.
"""
from __future__ import annotations

import logging
from typing import Any, Tuple

log = logging.getLogger("bridge.bale.gateway")


class BaleBotGateway:
    """روی هر کلاینتی با get_chat/send_message/delete_message کار می‌کند
    (BotAPI ربات بله یا خودِ سلف) — برای resolve و تست دسترسی."""

    def __init__(self, api: Any) -> None:
        self.api = api

    # ───────────────────────────── resolve ─────────────────────────────
    async def resolve(self, ref: str) -> Tuple[str, str, str]:
        """ارجاع (@آیدی/شناسه) → (شناسهٔ رشته‌ای، برچسب، یوزرنیم)."""
        ref = (ref or "").strip()
        if ref.isdigit() or (ref.startswith("-") and ref[1:].isdigit()):
            chat_id = ref
        elif ref.startswith("@"):
            chat_id = ref
        else:
            chat_id = "@" + ref
        try:
            chat = await self.api.get_chat(chat_id)
        except Exception as e:
            raise ValueError(
                f"چت بله «{ref}» پیدا نشد ({e}). ربات بله باید در کانال/گروه عضو "
                "(ترجیحاً ادمین) باشد. برای کانال خصوصی، پیامی از آن را به ربات فوروارد "
                "کنید و آیدی عددی را بگیرید."
            ) from e
        username = (chat.get("username") or "").lstrip("@")
        label = chat.get("title") or chat.get("first_name") or username or ""
        return str(chat.get("id")), label, username

    # ───────────────────────────── پروب دسترسی ─────────────────────────────
    async def probe_access(self, chat_id: Any) -> Tuple[bool, str]:
        """ارسال و حذف پیام آزمایشی — سنجش واقعی اجازهٔ نوشتن."""
        try:
            res = await self.api.send_message(int(chat_id), "🔔 تست دسترسی پل")
            mid = (res or {}).get("message_id")
            if not mid:
                return False, "✘ ارسال ناموفق"
            try:
                await self.api.delete_message(int(chat_id), mid)
            except Exception:
                pass
            return True, "✔ دسترسی دارد (ارسال/حذف تست شد)"
        except Exception as e:
            return False, f"✘ {str(e)[:80]}"

    # ───────────────────────────── استاتیک‌ها ─────────────────────────────
    @staticmethod
    async def probe(api: Any, chat_id: Any) -> Tuple[bool, str]:
        """نسخهٔ بی‌حالت — برای فراخوانی بدون ساخت نمونه."""
        return await BaleBotGateway(api).probe_access(chat_id)
