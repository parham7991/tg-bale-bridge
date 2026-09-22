"""EditorEngine — ویرایش متن/کپشن و حذف (حذف با تاریخِ کش‌شده کار می‌کند)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..bot_api import BotAPIError
from .resolver import ResolverEngine
from .session import BaleSession

logger = logging.getLogger("bridge.bale.editor")


class EditorEngine:
    def __init__(self, session: BaleSession, resolver: ResolverEngine) -> None:
        self.s = session
        self.r = resolver

    async def edit_message_text(self, chat_id: Any, message_id: Any, text: str,
                                **kw: Any) -> dict:
        try:
            await self.s.ensure_started()
            cid = await self.r.resolve_id(chat_id)
            ct = await self.r.ensure_chat_type(cid)
            await self.s.client.edit_message(
                text=text, message_id=int(message_id), chat_id=cid, chat_type=ct)
            return {"ok": True, "message_id": int(message_id)}
        except Exception as exc:
            raise BotAPIError(f"edit_message failed: {exc}") from exc

    async def edit_message_caption(self, chat_id: Any, message_id: Any,
                                   caption: Optional[str], **kw: Any) -> dict:
        # RPC ویرایش، اسلات متن/کپشن را عوض می‌کند؛ ممکن است روی رسانه رد شود —
        # لایهٔ انتقال در آن صورت به حذف+ارسال مجدد فالبک می‌کند.
        return await self.edit_message_text(chat_id, message_id, caption or "", **kw)

    async def delete_message(self, chat_id: Any, message_id: Any) -> dict:
        try:
            await self.s.ensure_started()
            cid = await self.r.resolve_id(chat_id)
            ct = await self.r.ensure_chat_type(cid)
            date = self.s.date_for(cid, message_id)
            await self.s.client.delete_message(
                message_id=int(message_id),
                message_date=date,
                chat_id=cid,
                chat_type=ct,
            )
            return {"ok": True}
        except Exception as exc:
            raise BotAPIError(f"delete_message failed: {exc}") from exc
