"""SenderEngine — همهٔ ارسال‌ها با resolve + فالبک‌های کامل."""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from ..bot_api import BotAPIError
from .resolver import ResolverEngine
from .session import BaleSession
from .types_map import FileArg

logger = logging.getLogger("bridge.bale.sender")


class SenderEngine:
    def __init__(self, session: BaleSession, resolver: ResolverEngine) -> None:
        self.s = session
        self.r = resolver

    # ───────────────────────────── پایه ─────────────────────────────
    async def send_chat_action(self, chat_id: Any, action: str = "typing") -> None:
        return None  # در API داخلی بله اندیکاتور «در حال تایپ» در دسترس نیست

    async def forward_message(self, chat_id: Any, from_chat_id: Any,
                              message_id: Any, **kw: Any) -> dict:
        raise BotAPIError("forward_message در حالت سلف‌بات پشتیبانی نمی‌شود")

    async def send_message(self, chat_id: Any, text: str,
                           reply_to: Any = None, **kw: Any) -> dict:
        try:
            await self.s.ensure_started()
            cid = await self.r.resolve_id(chat_id)
            ct = await self.r.ensure_chat_type(cid)
            msg = await self.s.client.send_message(
                text=text, chat_id=cid, chat_type=ct,
                reply_to=self.r.reply_ref(cid, reply_to),
            )
            return self.s.snapshot_result(cid, msg)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"send_message failed: {exc}") from exc

    async def _send_media(
        self, method_name: str, file: FileArg, chat_id: Any,
        caption: Optional[str] = None, reply_to: Any = None,
        file_kw: str = "file", **kw: Any,
    ) -> dict:
        try:
            await self.s.ensure_started()
            cid = await self.r.resolve_id(chat_id)
            ct = await self.r.ensure_chat_type(cid)
            method = getattr(self.s.client, method_name)
            msg = await method(
                **{
                    file_kw: file,
                    "chat_id": cid,
                    "chat_type": ct,
                    "caption": caption or None,
                    "reply_to": self.r.reply_ref(cid, reply_to),
                }
            )
            return self.s.snapshot_result(cid, msg)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"{method_name} failed: {exc}") from exc

    # ───────────────────────────── رسانه‌ها ─────────────────────────────
    async def send_photo(self, chat_id: Any, photo: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_photo", photo, chat_id, caption,
                                      reply_to, file_kw="photo")

    async def send_video(self, chat_id: Any, video: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_video", video, chat_id, caption,
                                      reply_to, file_kw="video")

    async def send_voice(self, chat_id: Any, voice: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_voice", voice, chat_id, caption,
                                      reply_to, file_kw="voice")

    async def send_audio(self, chat_id: Any, audio: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_audio", audio, chat_id, caption,
                                      reply_to, file_kw="audio")

    async def send_document(self, chat_id: Any, document: FileArg, caption: Optional[str] = None,
                            reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_document", document, chat_id, caption, reply_to)

    async def send_animation(self, chat_id: Any, animation: FileArg, caption: Optional[str] = None,
                             reply_to: Any = None, **kw: Any) -> dict:
        try:
            return await self._send_media("send_gif", animation, chat_id, caption,
                                          reply_to, file_kw="gif")
        except BotAPIError:
            return await self._send_media("send_document", animation, chat_id, caption, reply_to)

    async def send_sticker(self, chat_id: Any, sticker: FileArg, reply_to: Any = None,
                           **kw: Any) -> dict:
        # send_sticker() انتظار شناسه استیکر دارد؛ فایل را به‌صورت سند می‌فرستیم.
        return await self._send_media("send_document", sticker, chat_id, None, reply_to)

    async def send_video_note(self, chat_id: Any, video_note: FileArg, reply_to: Any = None,
                              **kw: Any) -> dict:
        return await self._send_media("send_video", video_note, chat_id, None,
                                      reply_to, file_kw="video")

    # ───────────────────────────── فالبک‌های متنی ─────────────────────────────
    async def send_location(self, chat_id: Any, latitude: float, longitude: float,
                            reply_to: Any = None, **kw: Any) -> dict:
        link = f"https://maps.google.com/?q={latitude},{longitude}"
        return await self.send_message(chat_id, f"📍 {link}", reply_to=reply_to)

    async def send_venue(self, chat_id: Any, latitude: float, longitude: float, title: str,
                         address: str = "", reply_to: Any = None, **kw: Any) -> dict:
        link = f"https://maps.google.com/?q={latitude},{longitude}"
        return await self.send_message(chat_id, f"📍 {title}\n{address}\n{link}",
                                       reply_to=reply_to)

    async def send_contact(self, chat_id: Any, phone_number: str, first_name: str,
                           last_name: str = "", reply_to: Any = None, **kw: Any) -> dict:
        return await self.send_message(
            chat_id, f"👤 {first_name} {last_name}".strip() + f"\n{phone_number}",
            reply_to=reply_to)

    async def send_poll(self, chat_id: Any, question: str, options: List[str],
                        **kw: Any) -> dict:
        lines = "\n".join(f"▫️ {o}" for o in (options or []))
        return await self.send_message(chat_id, f"📊 {question}\n{lines}")

    async def send_dice(self, chat_id: Any, emoji: Optional[str] = None, **kw: Any) -> dict:
        return await self.send_message(chat_id, f"🎲 {emoji or ''}".strip())

    async def send_media_group(self, chat_id: Any, items: List[Tuple[str, FileArg]],
                               reply_to: Any = None, **kw: Any) -> List[dict]:
        results: List[dict] = []
        method_map = {
            "photo": self.send_photo,
            "video": self.send_video,
            "animation": self.send_animation,
            "document": self.send_document,
            "audio": self.send_audio,
            "voice": self.send_voice,
        }
        for item in items:
            kind, path = item[0], item[1]
            cap = item[2] if len(item) > 2 else None
            method = method_map.get(kind, self.send_document)
            results.append(await method(chat_id, path, caption=cap, reply_to=reply_to))
        return results
