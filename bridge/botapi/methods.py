"""MethodsEngine — متدهای پایهٔ Bot-API: حساب، چت، آپدیت، متن، ویرایش، حذف، فوروارد."""
from __future__ import annotations

from .transport import BotAPIError


class MethodsEngine:
    """همهٔ فراخوانی‌ها از ``api.call`` می‌گذرند (زنده — قابل پچ در تست)."""

    def __init__(self, api) -> None:
        self.api = api

    async def get_me(self):
        return await self.api.call("getMe")

    async def get_chat(self, chat_id):
        return await self.api.call("getChat", {"chat_id": chat_id})

    async def get_updates(self, offset: int | None = None, timeout: int = 30):
        return await self.api.call(
            "getUpdates", {"offset": offset, "timeout": timeout, "limit": 100})

    async def send_message(self, chat_id, text: str, reply_to: int | None = None,
                           reply_markup: dict | None = None):
        params = {"chat_id": chat_id, "text": text, "reply_to_message_id": reply_to}
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.api.call("sendMessage", params)

    async def send_chat_action(self, chat_id, action: str = "typing"):
        try:
            return await self.api.call(
                "sendChatAction", {"chat_id": chat_id, "action": action})
        except BotAPIError:
            return None

    async def edit_message_text(self, chat_id, message_id: int, text: str):
        return await self.api.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text,
        })

    async def edit_message_caption(self, chat_id, message_id: int, caption: str):
        return await self.api.call("editMessageCaption", {
            "chat_id": chat_id, "message_id": message_id, "caption": caption,
        })

    async def delete_message(self, chat_id, message_id: int):
        return await self.api.call("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id,
        })

    async def forward_message(self, chat_id, from_chat_id, message_id: int):
        return await self.api.call("forwardMessage", {
            "chat_id": chat_id, "from_chat_id": from_chat_id,
            "message_id": message_id,
        })
