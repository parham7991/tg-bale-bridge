"""ProfileEngine — هویت حساب و اطلاعات چت‌ها (get_me / get_chat)."""
from __future__ import annotations

import logging
from typing import Union

from ..bot_api import BotAPIError
from .resolver import ResolverEngine
from .session import BaleSession
from .types_map import unwrap

logger = logging.getLogger("bridge.bale.profile")


class ProfileEngine:
    def __init__(self, session: BaleSession, resolver: ResolverEngine) -> None:
        self.s = session
        self.r = resolver

    async def get_me(self) -> dict:
        try:
            await self.s.ensure_started()
            info = getattr(self.s.client, "me", None)
            if info is None:
                info = await self.s.client.get_me()
        except Exception as exc:
            raise BotAPIError(f"get_me failed: {exc}") from exc
        uid = int(getattr(info, "id", 0) or 0)
        user_obj = getattr(info, "user", None)  # ClientData.user → UserAuth
        name = unwrap(getattr(user_obj, "name", None)) or getattr(info, "name", None)
        username = (unwrap(getattr(user_obj, "username", None))
                    or getattr(info, "username", None))
        if uid and (not name or not username):
            try:
                from aiobale.enums import ChatType

                user = await self.s.client.load_user(uid, ChatType.PRIVATE)
                name = name or unwrap(getattr(user, "name", None))
                username = username or unwrap(getattr(user, "username", None))
            except Exception:
                pass
        return {
            "id": uid,
            "is_bot": False,
            "first_name": str(name or "Bale user"),
            "username": str(username).lstrip("@") if username else None,
        }

    async def get_chat(self, ref: Union[str, int]) -> dict:
        await self.s.ensure_started()
        try:
            cid = await self.r.resolve_id(ref)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"get_chat failed for {ref!r}: {exc}") from exc
        out: dict = {"id": cid, "type": self.s.chat_types.get(str(cid))}
        try:
            full = await self.s.client.get_full_group(cid)
            gt = str(getattr(full, "group_type", "") or "").upper()
            name = "channel" if "CHANNEL" in gt else "group"
            out["type"] = name
            out["title"] = unwrap(getattr(full, "title", None))
            uname = unwrap(getattr(full, "username", None))
            if uname:
                out["username"] = str(uname).lstrip("@")
        except Exception:
            try:
                user = await self.s.client.load_user(cid)
                out["type"] = "private"
                out["title"] = unwrap(getattr(user, "name", None))
                uname = unwrap(getattr(user, "username", None))
                if uname:
                    out["username"] = str(uname).lstrip("@")
            except Exception:
                out.setdefault("type", out.get("type") or "private")
        self.s.chat_types[str(cid)] = out["type"]
        self.s.note_chat(cid, out)
        return out
