"""facade.py — BaleUserAPI: ریشهٔ ترکیب موتورهای بله.

همان سطح عمومی همیشه‌سبز (drop-in جای BotAPI)؛ حالا هر بخش از موتور مربوطه‌اش
می‌آید و facade فقط سیم‌کشی است.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

from .admin_ops import AdminOpsEngine
from .editor import EditorEngine
from .events import EventsEngine
from .files import FilesEngine
from .normalize import NormalizeEngine
from .profile import ProfileEngine
from .resolver import ResolverEngine
from .sender import SenderEngine
from .session import BaleSession
from .types_map import FileArg

logger = logging.getLogger("bridge.bale.facade")


class BaleUserAPI:
    """فاساد کامل سلف بله — BotAPI-compatible façade (حساب کاربری با aiobale)."""

    #: BotAPI این رویداد را ندارد؛ سلف‌بات بله دارد (برای همگام‌سازی حذف).
    has_delete_events = True

    def __init__(
        self,
        session_file: Optional[Union[str, Path]] = None,
        phone_number: Optional[str] = None,
        token: Optional[str] = None,
        db: Any = None,
        client: Any = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.session = BaleSession(
            db=db, client=client, session_file=session_file,
            phone_number=phone_number, token=token, user_agent=user_agent,
        )
        self.resolver = ResolverEngine(self.session)
        self.normalizer = NormalizeEngine(self.session)
        self.events = EventsEngine(self.session, self.normalizer)
        self.sender = SenderEngine(self.session, self.resolver)
        self.editor = EditorEngine(self.session, self.resolver)
        self.file_engine = FilesEngine(self.session)
        self.admin_ops = AdminOpsEngine(self.session, self.resolver)
        self.profile = ProfileEngine(self.session, self.resolver)
        self.events.register()

    # ───────────────── سازگاری با کد قدیمی (ویژگی‌های session) ─────────────────
    @property
    def _db(self):
        return self.session.db

    @property
    def client(self):
        return self.session.client

    @property
    def dp(self):
        return self.session.dp

    @property
    def _files(self):
        return self.session.files

    @property
    def _dates(self):
        return self.session.dates

    @property
    def _chat_types(self):
        return self.session.chat_types

    @property
    def _chat_meta(self):
        return self.session.chat_meta

    @property
    def _id_cache(self):
        return self.session.id_cache

    @property
    def _handler(self):
        return self.session.handler

    @_handler.setter
    def _handler(self, fn) -> None:
        self.session.handler = fn

    @property
    def _offset(self):
        return self.session.offset

    @_offset.setter
    def _offset(self, v) -> None:
        self.session.offset = v

    @property
    def _started(self):
        return self.session.started

    @_started.setter
    def _started(self, v) -> None:
        self.session.started = v

    # ───────────────── چرخهٔ حیات ─────────────────
    async def start(self) -> None:
        """اتصال پس‌زمینه (start با run_in_background=True بلاک نمی‌کند)."""
        await self.session.start()

    async def _ensure_started(self) -> None:
        await self.session.ensure_started()

    async def close(self) -> None:
        await self.session.stop()

    async def listen(self, handler: Callable[..., Any], offset: int = 0,
                     timeout: int = 30) -> None:
        await self.events.listen(handler, offset=offset, timeout=timeout)

    # ───────────────── رویدادها / نرمال‌سازی ─────────────────
    def normalize(self, msg: Any) -> dict:
        return self.normalizer.normalize(msg)

    async def _on_message(self, msg: Any) -> None:
        await self.events.on_message(msg)

    async def _on_edited(self, msg: Any) -> None:
        await self.events.on_edited(msg)

    async def _on_deleted(self, selected: Any) -> None:
        await self.events.on_deleted(selected)

    # ───────────────── resolver / session delegateها ─────────────────
    async def _resolve_id(self, chat_id: Any) -> int:
        return await self.resolver.resolve_id(chat_id)

    async def _resolve_user(self, user_ref: Any) -> Tuple[int, Any]:
        return await self.resolver.resolve_user(user_ref)

    async def _ensure_chat_type(self, chat_id: Any) -> Any:
        return await self.resolver.ensure_chat_type(chat_id)

    def _chat_type_of(self, chat_id: Any) -> str:
        return self.resolver.chat_type_of(chat_id)

    def _ct_enum(self, chat_id: Any) -> Any:
        return self.resolver.ct_enum(chat_id)

    def _reply_ref(self, chat_id: Any, reply_to: Any) -> Any:
        return self.resolver.reply_ref(chat_id, reply_to)

    def _result_for(self, chat_id: Any, msg: Any) -> dict:
        return self.session.snapshot_result(chat_id, msg)

    def _remember_date(self, chat_id: Any, msg_id: Any, date: Any) -> None:
        self.session.remember_date(chat_id, msg_id, date)

    def _remember_file(self, file_id: Any, access_hash: Any) -> None:
        self.session.remember_file(file_id, access_hash)

    def _date_for(self, chat_id: Any, msg_id: Any) -> int:
        return self.session.date_for(chat_id, msg_id)

    def _access_hash_for(self, file_id: Any) -> Optional[int]:
        return self.session.access_hash_for(file_id)

    def _bump(self) -> int:
        return self.session.bump()

    async def _emit(self, upd: dict) -> None:
        await self.session.emit(upd)

    # ───────────────── ارسال ─────────────────
    async def send_chat_action(self, chat_id: Any, action: str = "typing") -> None:
        return await self.sender.send_chat_action(chat_id, action)

    async def forward_message(self, chat_id: Any, from_chat_id: Any,
                              message_id: Any, **kw: Any) -> dict:
        return await self.sender.forward_message(chat_id, from_chat_id, message_id, **kw)

    async def send_message(self, chat_id: Any, text: str,
                           reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_message(chat_id, text, reply_to, **kw)

    async def _send_media(self, method_name: str, file: FileArg, chat_id: Any,
                          caption: Optional[str] = None, reply_to: Any = None,
                          file_kw: str = "file", **kw: Any) -> dict:
        return await self.sender._send_media(method_name, file, chat_id, caption,
                                             reply_to, file_kw, **kw)

    async def send_photo(self, chat_id: Any, photo: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_photo(chat_id, photo, caption, reply_to, **kw)

    async def send_video(self, chat_id: Any, video: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_video(chat_id, video, caption, reply_to, **kw)

    async def send_voice(self, chat_id: Any, voice: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_voice(chat_id, voice, caption, reply_to, **kw)

    async def send_audio(self, chat_id: Any, audio: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_audio(chat_id, audio, caption, reply_to, **kw)

    async def send_document(self, chat_id: Any, document: FileArg, caption: Optional[str] = None,
                            reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_document(chat_id, document, caption, reply_to, **kw)

    async def send_animation(self, chat_id: Any, animation: FileArg, caption: Optional[str] = None,
                             reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_animation(chat_id, animation, caption, reply_to, **kw)

    async def send_sticker(self, chat_id: Any, sticker: FileArg, reply_to: Any = None,
                           **kw: Any) -> dict:
        return await self.sender.send_sticker(chat_id, sticker, reply_to, **kw)

    async def send_video_note(self, chat_id: Any, video_note: FileArg, reply_to: Any = None,
                              **kw: Any) -> dict:
        return await self.sender.send_video_note(chat_id, video_note, reply_to, **kw)

    async def send_location(self, chat_id: Any, latitude: float, longitude: float,
                            reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_location(chat_id, latitude, longitude, reply_to, **kw)

    async def send_venue(self, chat_id: Any, latitude: float, longitude: float, title: str,
                         address: str = "", reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_venue(chat_id, latitude, longitude, title,
                                            address, reply_to, **kw)

    async def send_contact(self, chat_id: Any, phone_number: str, first_name: str,
                           last_name: str = "", reply_to: Any = None, **kw: Any) -> dict:
        return await self.sender.send_contact(chat_id, phone_number, first_name,
                                              last_name, reply_to, **kw)

    async def send_poll(self, chat_id: Any, question: str, options: List[str],
                        **kw: Any) -> dict:
        return await self.sender.send_poll(chat_id, question, options, **kw)

    async def send_dice(self, chat_id: Any, emoji: Optional[str] = None, **kw: Any) -> dict:
        return await self.sender.send_dice(chat_id, emoji, **kw)

    async def send_media_group(self, chat_id: Any, items: List[Tuple[str, FileArg]],
                               reply_to: Any = None, **kw: Any) -> List[dict]:
        return await self.sender.send_media_group(chat_id, items, reply_to, **kw)

    # ───────────────── ویرایش/حذف ─────────────────
    async def edit_message_text(self, chat_id: Any, message_id: Any, text: str,
                                **kw: Any) -> dict:
        return await self.editor.edit_message_text(chat_id, message_id, text, **kw)

    async def edit_message_caption(self, chat_id: Any, message_id: Any,
                                   caption: Optional[str], **kw: Any) -> dict:
        return await self.editor.edit_message_caption(chat_id, message_id, caption, **kw)

    async def delete_message(self, chat_id: Any, message_id: Any) -> dict:
        return await self.editor.delete_message(chat_id, message_id)

    # ───────────────── فایل‌ها ─────────────────
    async def download_file(self, file_id: Any, dest: Union[str, Path],
                            **kw: Any) -> Union[str, Path]:
        return await self.file_engine.download_file(file_id, dest, **kw)

    async def get_file(self, file_id: Any, **kw: Any) -> dict:
        return await self.file_engine.get_file(file_id, **kw)

    # ───────────────── ادمین‌کردن ─────────────────
    async def add_admin(self, chat_ref: Any, user_ref: Any,
                        admin_name: Optional[str] = None) -> dict:
        return await self.admin_ops.add_admin(chat_ref, user_ref, admin_name)

    # ───────────────── هویت/چت ─────────────────
    async def get_me(self) -> dict:
        return await self.profile.get_me()

    async def get_chat(self, ref: Union[str, int]) -> dict:
        return await self.profile.get_chat(ref)
