"""ResolverEngine — تبدیل ارجاع‌ها: شناسه، @یوزرنیم، نوع چت، ریپلای، کاربر."""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from aiobale.enums import ChatType
from aiobale.types import InfoMessage, Peer

from ..bot_api import BotAPIError
from .session import BaleSession
from .types_map import extract_id, extract_user, peer_type

logger = logging.getLogger("bridge.bale.resolver")

_NAME_CHAT_TYPES = {
    "private": ChatType.PRIVATE,
    "group": ChatType.GROUP,
    "channel": ChatType.CHANNEL,
}


class ResolverEngine:
    def __init__(self, session: BaleSession) -> None:
        self.s = session

    # ── نوع چت ──
    def chat_type_of(self, chat_id: Any) -> str:
        return self.s.chat_type_of(chat_id)

    def ct_enum(self, chat_id: Any) -> ChatType:
        return _NAME_CHAT_TYPES.get(self.chat_type_of(chat_id), ChatType.GROUP)

    async def ensure_chat_type(self, chat_id: Any) -> ChatType:
        """نوع چت را از کش یا با get_full_group تعیین و ثبت می‌کند."""
        key = str(chat_id)
        if key in self.s.chat_types:
            return _NAME_CHAT_TYPES.get(self.s.chat_types[key], ChatType.GROUP)
        try:
            full = await self.s.client.get_full_group(int(chat_id))
        except Exception:
            self.s.chat_types.setdefault(key, "private")
            return ChatType.PRIVATE
        # group_type یک IntEnum است (GROUP=0, CHANNEL=1) — str() عدد می‌دهد!
        gt = getattr(full, "group_type", None)
        is_channel = (gt == 1) or ("CHANNEL" in str(gt).upper())
        name = "channel" if is_channel else "group"
        self.s.chat_types[key] = name
        self.s.note_chat(chat_id, {"type": name, "title": getattr(full, "title", None)})
        return _NAME_CHAT_TYPES[name]

    # ── شناسه ──
    async def resolve_id(self, chat_id: Any) -> int:
        if isinstance(chat_id, int):
            return chat_id
        key = str(chat_id).strip()
        if key.lstrip("-").isdigit():
            return int(key)
        if key in self.s.id_cache:
            return self.s.id_cache[key]
        found = await self.s.client.search_username(key.lstrip("@"))
        cid = extract_id(found)
        if not cid:
            raise BotAPIError(f"chat not found: {chat_id!r}")
        self.s.id_cache[key] = cid
        return cid

    # ── کاربر/ربات ──
    async def resolve_user(self, user_ref: Any) -> Tuple[int, Any]:
        if isinstance(user_ref, int):
            return user_ref, None
        key = str(user_ref).strip().lstrip("@")
        found = await self.s.client.search_username(key)
        user = extract_user(found)
        if user is None:
            raise BotAPIError(f"user not found: {user_ref!r}")
        uid = extract_id(user)
        if not uid:
            raise BotAPIError(f"user id not resolved: {user_ref!r}")
        return int(uid), user

    # ── ریپلای ──
    def reply_ref(self, chat_id: Any, reply_to: Any) -> Optional[InfoMessage]:
        if not reply_to:
            return None
        try:
            return InfoMessage(
                peer=Peer(type=peer_type(self.chat_type_of(chat_id)), id=int(chat_id)),
                message_id=int(reply_to),
                date=self.s.date_for(chat_id, reply_to),
            )
        except Exception:
            return None
