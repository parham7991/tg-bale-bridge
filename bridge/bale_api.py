"""کلاینت HTTP برای API بازوی بله (https://docs.bale.ai) با پشتیبانی آپلود فایل."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import aiohttp

log = logging.getLogger("bale")


class BaleError(Exception):
    def __init__(self, description: str, error_code: int = 0, parameters=None):
        super().__init__(description)
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}


class BaleAPI:
    def __init__(self, token: str, base: str = "https://tapi.bale.ai"):
        self.token = token
        self.base = base.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    # ---------- زیرساخت ----------
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=180, sock_connect=30)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def url(self, method: str) -> str:
        return f"{self.base}/bot{self.token}/{method}"

    def file_url(self, file_path: str) -> str:
        return f"{self.base}/file/bot{self.token}/{file_path}"

    async def call(self, method: str, params: dict | None = None, files: dict | None = None):
        """فراخوانی متد. `files`: نام_فیلد -> مسیر فایل (multipart)."""
        params = {k: v for k, v in (params or {}).items() if v is not None}
        session = await self._get_session()

        for attempt in range(4):
            try:
                if files:
                    form = aiohttp.FormData()
                    for name, value in params.items():
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False)
                        form.add_field(name, str(value))
                    for name, path in (files or {}).items():
                        path = Path(path)
                        form.add_field(
                            name,
                            path.open("rb"),
                            filename=path.name,
                            content_type="application/octet-stream",
                        )
                    async with session.post(self.url(method), data=form) as resp:
                        payload = await resp.json(content_type=None)
                else:
                    async with session.post(self.url(method), json=params) as resp:
                        payload = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise BaleError(f"خطای شبکه در {method}: {e}") from e

            if payload.get("ok"):
                return payload.get("result")

            desc = payload.get("description", "خطای ناشناخته بله")
            code = payload.get("error_code", 0)
            resp_params = payload.get("parameters") or {}
            retry_after = resp_params.get("retry_after")
            if retry_after and attempt < 3:
                log.warning("rate limit on %s — retry after %ss", method, retry_after)
                await asyncio.sleep(float(retry_after) + 0.5)
                continue
            raise BaleError(desc, code, resp_params)

        raise BaleError(f"{method} پس از چند تلاش ناموفق بود")

    # ---------- متدهای عمومی ----------
    async def get_me(self):
        return await self.call("getMe")

    async def get_chat(self, chat_id):
        return await self.call("getChat", {"chat_id": chat_id})

    async def get_updates(self, offset: int | None = None, timeout: int = 30):
        return await self.call("getUpdates", {"offset": offset, "timeout": timeout, "limit": 100})

    async def send_message(self, chat_id, text: str, reply_to: int | None = None):
        return await self.call("sendMessage", {
            "chat_id": chat_id, "text": text, "reply_to_message_id": reply_to,
        })

    async def send_chat_action(self, chat_id, action: str = "typing"):
        try:
            return await self.call("sendChatAction", {"chat_id": chat_id, "action": action})
        except BaleError:
            return None

    async def edit_message_text(self, chat_id, message_id: int, text: str):
        return await self.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text,
        })

    async def edit_message_caption(self, chat_id, message_id: int, caption: str):
        return await self.call("editMessageCaption", {
            "chat_id": chat_id, "message_id": message_id, "caption": caption,
        })

    async def delete_message(self, chat_id, message_id: int):
        return await self.call("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id,
        })

    async def forward_message(self, chat_id, from_chat_id, message_id: int):
        return await self.call("forwardMessage", {
            "chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id,
        })

    # ---------- ارسال رسانه ----------
    async def _send_media(self, method: str, field: str, chat_id, path,
                          caption: str | None = None, reply_to: int | None = None,
                          extra: dict | None = None):
        params = {"chat_id": chat_id, "caption": caption, "reply_to_message_id": reply_to}
        if extra:
            params.update(extra)
        return await self.call(method, params, files={field: path})

    async def send_photo(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media("sendPhoto", "photo", chat_id, path, caption, reply_to)

    async def send_video(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media("sendVideo", "video", chat_id, path, caption, reply_to)

    async def send_animation(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media(
            "sendAnimation", "animation", chat_id, path, caption, reply_to)

    async def send_audio(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media("sendAudio", "audio", chat_id, path, caption, reply_to)

    async def send_voice(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media("sendVoice", "voice", chat_id, path, caption, reply_to)

    async def send_document(self, chat_id, path, caption=None, reply_to=None):
        return await self._send_media("sendDocument", "document", chat_id, path, caption, reply_to)

    async def send_sticker(self, chat_id, path, reply_to=None):
        return await self._send_media("sendSticker", "sticker", chat_id, path, None, reply_to)

    async def send_video_note(self, chat_id, path, reply_to=None):
        return await self._send_media("sendVideoNote", "video_note", chat_id, path, None, reply_to)

    async def send_location(self, chat_id, latitude, longitude, reply_to=None):
        return await self.call("sendLocation", {
            "chat_id": chat_id, "latitude": latitude, "longitude": longitude,
            "reply_to_message_id": reply_to,
        })

    async def send_contact(self, chat_id, phone_number, first_name,
                           last_name: str = "", reply_to=None):
        return await self.call("sendContact", {
            "chat_id": chat_id, "phone_number": phone_number,
            "first_name": first_name, "last_name": last_name or "",
            "reply_to_message_id": reply_to,
        })

    async def send_media_group(self, chat_id, items, reply_to=None):
        """items: لیست (نوع، مسیر فایل، کپشن) با نوع photo/video/document/audio."""
        form_files = {}
        media = []
        for i, (mtype, path, caption) in enumerate(items):
            name = f"f{i}"
            form_files[name] = path
            media.append({
                "type": mtype,
                "media": f"attach://{name}",
                "caption": (caption or "")[:1024] or None,
            })
        return await self.call("sendMediaGroup", {
            "chat_id": chat_id,
            "media": media,
            "reply_to_message_id": reply_to,
        }, files=form_files)

    # ---------- فایل ----------
    async def get_file(self, file_id: str):
        return await self.call("getFile", {"file_id": file_id})

    async def download_file(self, file_id: str, dest: Path) -> Path:
        info = await self.get_file(file_id)
        file_path = info.get("file_path")
        if not file_path:
            raise BaleError("file_path در پاسخ getFile نبود")
        session = await self._get_session()
        dest = Path(dest)
        async with session.get(self.file_url(file_path)) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                async for chunk in resp.content.iter_chunked(1 << 16):
                    f.write(chunk)
        return dest

    # ---------- دریافت آپدیت ----------
    async def listen(self, handler, offset: int | None = None, timeout: int = 30):
        """long-polling بی‌نهایت؛ handler(update) باید coroutine باشد."""
        if offset is None:
            # رد کردن انباشت قدیمی: گرفتن انتهای صف
            pending = await self.get_updates(offset=-1, timeout=0)
            if pending:
                offset = pending[-1]["update_id"] + 1
            else:
                offset = 0
        while True:
            try:
                updates = await self.get_updates(offset=offset, timeout=timeout)
            except BaleError as e:
                log.error("getUpdates failed: %s", e)
                await asyncio.sleep(5)
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                log.error("getUpdates network error: %s", e)
                await asyncio.sleep(5)
                continue
            for upd in updates or []:
                offset = max(offset, upd["update_id"] + 1)
                try:
                    await handler(upd, offset)
                except Exception:
                    log.exception("handler error")
