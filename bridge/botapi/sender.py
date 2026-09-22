"""SenderEngine — ارسال رسانه‌ها و آیتم‌های خاص: عکس/ویدیو/…، لوکیشن، مخاطب، آلبوم."""
from __future__ import annotations

from .types_map import MEDIA_METHODS, build_media_group


class SenderEngine:
    """هر رسانه‌ای یک متد — همه از ``api.call`` با فایل multipart."""

    def __init__(self, api) -> None:
        self.api = api

    async def send_media(self, kind: str, chat_id, path, caption=None, reply_to=None,
                         extra: dict | None = None):
        """ارسال بر اساس نوع — از جدول نگاشت (method, field)."""
        method, field = MEDIA_METHODS[kind]
        params = {"chat_id": chat_id, "caption": caption, "reply_to_message_id": reply_to}
        if extra:
            params.update(extra)
        return await self.api.call(method, params, files={field: path})

    # نام تاریخی
    async def _send_media(self, method: str, field: str, chat_id, path,
                          caption: str | None = None, reply_to: int | None = None,
                          extra: dict | None = None):
        params = {"chat_id": chat_id, "caption": caption, "reply_to_message_id": reply_to}
        if extra:
            params.update(extra)
        return await self.api.call(method, params, files={field: path})

    async def send_photo(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("photo", chat_id, path, caption, reply_to)

    async def send_video(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("video", chat_id, path, caption, reply_to)

    async def send_animation(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("animation", chat_id, path, caption, reply_to)

    async def send_audio(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("audio", chat_id, path, caption, reply_to)

    async def send_voice(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("voice", chat_id, path, caption, reply_to)

    async def send_document(self, chat_id, path, caption=None, reply_to=None):
        return await self.api.send_media("document", chat_id, path, caption, reply_to)

    async def send_sticker(self, chat_id, path, reply_to=None):
        return await self.api.send_media("sticker", chat_id, path, None, reply_to)

    async def send_video_note(self, chat_id, path, reply_to=None):
        return await self.api.send_media("video_note", chat_id, path, None, reply_to)

    async def send_location(self, chat_id, latitude, longitude, reply_to=None):
        return await self.api.call("sendLocation", {
            "chat_id": chat_id, "latitude": latitude, "longitude": longitude,
            "reply_to_message_id": reply_to,
        })

    async def send_contact(self, chat_id, phone_number, first_name,
                           last_name: str = "", reply_to=None):
        return await self.api.call("sendContact", {
            "chat_id": chat_id, "phone_number": phone_number,
            "first_name": first_name, "last_name": last_name or "",
            "reply_to_message_id": reply_to,
        })

    async def send_media_group(self, chat_id, items, reply_to=None):
        """items: لیست (نوع، مسیر فایل، کپشن) با نوع photo/video/document/audio."""
        form_files, media = build_media_group(items)
        return await self.api.call("sendMediaGroup", {
            "chat_id": chat_id,
            "media": media,
            "reply_to_message_id": reply_to,
        }, files=form_files)
