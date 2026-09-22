"""AdminOpsEngine — ادمین‌کردن: سلفِ ادمین، ربات/کاربر را اضافه و ادمین می‌کند.

زنجیرهٔ واقعی (مانند کاری که ادمین انسانی در اپ می‌کند):
    search_username → invite_user → make_user_admin
«از قبل عضو» نادیده گرفته می‌شود؛ رد شدن سرور به‌صورت خطای واضح بالا می‌آید.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from aiobale.enums import ChatType

from ..bot_api import BotAPIError
from .resolver import ResolverEngine
from .session import BaleSession

logger = logging.getLogger("bridge.bale.admin_ops")

_ALREADY_MEMBER_HINTS = ("already", "member", "exists", "invite")


class AdminOpsEngine:
    def __init__(self, session: BaleSession, resolver: ResolverEngine) -> None:
        self.s = session
        self.r = resolver

    async def add_admin(self, chat_ref: Any, user_ref: Any,
                        admin_name: Optional[str] = None) -> Dict[str, Any]:
        """کاربر/ربات را به کانال/گروه اضافه و ادمین می‌کند.

        پیش‌نیاز: خودِ سلف در آن کانال ادمین باشد. اگر هدف از قبل عضو بود،
        خطای عضویت نادیده گرفته می‌شود و فقط ارتقا انجام می‌شود.
        """
        await self.s.ensure_started()
        cid = await self.r.resolve_id(chat_ref)
        ct = await self.r.ensure_chat_type(cid)
        if ct == ChatType.PRIVATE:
            raise BotAPIError("در چت خصوصی نمی‌توان ادمین اضافه کرد")
        user_id, user_obj = await self.r.resolve_user(user_ref)
        try:
            try:
                await self.s.client.invite_user(
                    cid, user_obj if user_obj is not None else user_id)
            except Exception as exc:
                msg = str(exc).lower()
                if not any(t in msg for t in _ALREADY_MEMBER_HINTS):
                    raise
            await self.s.client.make_user_admin(cid, user_id, admin_name)
            return {"ok": True, "chat_id": cid, "user_id": user_id}
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"add_admin failed: {exc}") from exc
