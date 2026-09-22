"""BotAPI — نمای سازگاری کلاینت Bot-API (ریشهٔ ترکیب بستهٔ botapi).

سطح عمومی دقیقاً مثل قبل: ``BotAPI(token, base="https://tapi.bale.ai")`` با
``call / url / file_url / get_me / get_chat / get_updates / send_* / edit_* /
delete_message / forward_message / send_media_group / get_file / download_file /
listen / close`` — اما داخل، هر بخش به موتور خودش تفویض می‌شود:

    types_map  → نگاشت‌های خالص (URL، جدول رسانه، آلبوم)
    session.py → BotAPISession (نشست aiohttp)
    transport.py → CallEngine (retry + rate-limit + multipart) + BotAPIError
    methods.py → MethodsEngine (متدهای پایه)
    sender.py  → SenderEngine (رسانه‌ها)
    files.py   → FilesEngine (دانلود)
    events.py  → ListenEngine (long-polling)

نکته: همهٔ موتورها از طریق ``api.call`` (زنده) فراخوانی می‌کنند — پچ‌کردن
``call`` روی نما در تست‌ها روی همهٔ متدها اثر می‌گذارد.
"""
from __future__ import annotations

from pathlib import Path

from .events import ListenEngine
from .files import FilesEngine
from .methods import MethodsEngine
from .sender import SenderEngine
from .session import BotAPISession
from .transport import BotAPIError, CallEngine
from .types_map import BASE_DEFAULT, build_file_url, build_url, normalize_base


class BotAPI:
    """کلاینت HTTP برای Bot-API بله/تلگرام با پشتیبانی آپلود فایل."""

    def __init__(self, token: str, base: str = BASE_DEFAULT):
        self.token = token
        self.base = normalize_base(base)
        self.me: dict = {}
        # ── موتورها ──
        self.session_engine = BotAPISession()
        self.transport = CallEngine(self)
        self.methods = MethodsEngine(self)
        self.sender = SenderEngine(self)
        self.files = FilesEngine(self)
        self.listen_engine = ListenEngine(self)

    # ---------- زیرساخت ----------
    @property
    def _session(self):
        """سازگاری: نشست aiohttp جاری (یا None)."""
        return self.session_engine.session

    async def _get_session(self):
        return await self.session_engine.get()

    async def close(self):
        await self.session_engine.close()

    def url(self, method: str) -> str:
        return build_url(self.base, self.token, method)

    def file_url(self, file_path: str) -> str:
        return build_file_url(self.base, self.token, file_path)

    async def call(self, method: str, params: dict | None = None,
                   files: dict | None = None):
        """تفویض به موتور انتقال — retry + rate-limit + multipart/json."""
        return await self.transport.call(method, params, files)

    # ---------- متدهای عمومی ----------
    async def get_me(self):
        return await self.methods.get_me()

    async def get_chat(self, chat_id):
        return await self.methods.get_chat(chat_id)

    async def get_updates(self, offset: int | None = None, timeout: int = 30):
        return await self.methods.get_updates(offset, timeout)

    async def send_message(self, chat_id, text: str, reply_to: int | None = None,
                           reply_markup: dict | None = None):
        return await self.methods.send_message(chat_id, text, reply_to, reply_markup)

    async def send_chat_action(self, chat_id, action: str = "typing"):
        return await self.methods.send_chat_action(chat_id, action)

    async def edit_message_text(self, chat_id, message_id: int, text: str):
        return await self.methods.edit_message_text(chat_id, message_id, text)

    async def edit_message_caption(self, chat_id, message_id: int, caption: str):
        return await self.methods.edit_message_caption(chat_id, message_id, caption)

    async def delete_message(self, chat_id, message_id: int):
        return await self.methods.delete_message(chat_id, message_id)

    async def forward_message(self, chat_id, from_chat_id, message_id: int):
        return await self.methods.forward_message(chat_id, from_chat_id, message_id)

    # ---------- ارسال رسانه ----------
    async def send_media(self, kind: str, chat_id, path, caption=None, reply_to=None,
                         extra: dict | None = None):
        """ارسال بر اساس نوع — از جدول نگاشت (method, field)."""
        return await self.sender.send_media(kind, chat_id, path, caption, reply_to,
                                            extra)

    async def _send_media(self, method: str, field: str, chat_id, path,
                          caption: str | None = None, reply_to: int | None = None,
                          extra: dict | None = None):
        return await self.sender._send_media(method, field, chat_id, path,
                                             caption, reply_to, extra)

    async def send_photo(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_photo(chat_id, path, caption, reply_to)

    async def send_video(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_video(chat_id, path, caption, reply_to)

    async def send_animation(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_animation(chat_id, path, caption, reply_to)

    async def send_audio(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_audio(chat_id, path, caption, reply_to)

    async def send_voice(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_voice(chat_id, path, caption, reply_to)

    async def send_document(self, chat_id, path, caption=None, reply_to=None):
        return await self.sender.send_document(chat_id, path, caption, reply_to)

    async def send_sticker(self, chat_id, path, reply_to=None):
        return await self.sender.send_sticker(chat_id, path, reply_to)

    async def send_video_note(self, chat_id, path, reply_to=None):
        return await self.sender.send_video_note(chat_id, path, reply_to)

    async def send_location(self, chat_id, latitude, longitude, reply_to=None):
        return await self.sender.send_location(chat_id, latitude, longitude, reply_to)

    async def send_contact(self, chat_id, phone_number, first_name,
                           last_name: str = "", reply_to=None):
        return await self.sender.send_contact(chat_id, phone_number, first_name,
                                              last_name, reply_to)

    async def send_media_group(self, chat_id, items, reply_to=None):
        return await self.sender.send_media_group(chat_id, items, reply_to)

    # ---------- فایل ----------
    async def get_file(self, file_id: str):
        return await self.files.get_file(file_id)

    async def download_file(self, file_id: str, dest: Path) -> Path:
        return await self.files.download_file(file_id, dest)

    # ---------- دریافت آپدیت ----------
    async def listen(self, handler, offset: int | None = None, timeout: int = 30):
        """long-polling بی‌نهایت؛ handler(update, offset) باید coroutine باشد."""
        await self.listen_engine.listen(handler, offset, timeout)


__all__ = ["BotAPI", "BotAPIError"]
