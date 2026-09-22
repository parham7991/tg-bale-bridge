"""Bale «selfbot» adapter — user account on the Bale network via **aiobale**.

:class:`BaleUserAPI` is a drop-in replacement for :class:`bridge.bot_api.BotAPI`
(send_*/edit_*/delete_*/get_file/get_me/get_chat/listen) backed by a *logged-in
Bale user account* instead of a bot.

Why does this exist?  New Bale versions refuse to add bots to channels (and even
block saving a bot as a contact), so a bot can never reliably *write* to a
channel.  A user account — your own phone number's account — is already a
member of every channel you follow and can post wherever it has the right to.
The unofficial ``aiobale`` library (PyPI ``aiobale-py``) speaks Bale's real
protocol (WebSocket + protobuf) and supports user accounts natively.

Everything is best-effort mapped onto the *bot-API shape* the rest of the
bridge speaks:

* ``aiobale.types.Message`` → ``{"message_id", "date", "chat", "from",
  "text"|"photo"|"video"|"voice"|"audio"|"animation"|…, "caption",
  "reply_to_message"}`` — one unified ``document`` payload is classified into
  photo/video/voice/audio/animation/document by mime-type;
* deletion events (``message_deleted``) → the pseudo-update
  ``{"deleted_messages": {"chat": {...}, "message_ids": [...]}}`` — something
  the official Bot API can never deliver.  This unlocks **Bale→Telegram delete
  sync** in user mode.

Honest limitations of the selfbot mode:

* aiobale exposes no album id → a Bale album arrives as single messages;
* no forward-origin metadata → forwarded posts lose their attribution header;
* sticker / video_note / location / contact / poll sends degrade to a document
  or text message (the internal API has no upload helper for them);
* ``edit_message_caption`` reuses the text-edit RPC and may fail — the transfer
  layer then falls back to delete + re-send;
* private chats are *not* treated as an admin console (a stranger must never be
  auto-replied to from a human account) — use the Bale bot or the Telegram
  control bot for that.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from aiobale import Client, Dispatcher
from aiobale.enums import ChatType, PeerType
from aiobale.types import InfoMessage, Peer, SelectedMessages

from .bot_api import BotAPIError

logger = logging.getLogger("bridge.bale_user")

FileArg = Union[str, Path, bytes, Any]

#: aiobale ``ChatType`` int values → Bot-API chat types.
_CHAT_TYPE_NAMES = {
    1: "private",   # PRIVATE
    2: "group",     # GROUP
    3: "channel",   # CHANNEL
    4: "private",   # BOT
    5: "group",     # SUPER_GROUP
}

_NAME_CHAT_TYPES = {
    "private": ChatType.PRIVATE,
    "group": ChatType.GROUP,
    "channel": ChatType.CHANNEL,
}


def _chat_type_name(value: Any) -> str:
    try:
        v = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        v = 0
    return _CHAT_TYPE_NAMES.get(v, "private")


def _peer_type(chat_type_name: str) -> Any:
    return PeerType.GROUP if chat_type_name in ("group", "channel") else PeerType.PRIVATE


def _doc_name(doc: Any) -> str:
    name = getattr(doc, "name", None)
    if isinstance(name, dict):
        name = name.get("value") or name.get("name") or ""
    return str(name or "")


def _classify_document(doc: Any) -> str:
    """Map a unified aiobale ``DocumentMessage`` onto a Bot-API content type."""
    mime = (getattr(doc, "mime_type", "") or "").lower()
    name = _doc_name(doc).lower()
    ext = str(getattr(doc, "ext", "") or "").lower()
    if mime.startswith("image/"):
        if mime == "image/gif" or ext == "gif" or name.endswith(".gif"):
            return "animation"
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        if mime == "audio/ogg" or ext in ("ogg", "opus") or name.startswith("voice"):
            return "voice"
        return "audio"
    return "document"


def _unwrap(value: Any) -> Any:
    """باز کردن wrapperهای aiobale (مثل StringValue که مقدار در ``.value`` است)."""
    while value is not None and not isinstance(value, (str, int, float, bool)):
        inner = getattr(value, "value", None)
        if inner is None or inner is value:
            break
        value = inner
    return value


def _extract_id(obj: Any) -> int:
    for attr in ("id", "user_id", "chat_id"):
        v = getattr(obj, attr, None)
        if isinstance(v, int):
            return v
    for attr in ("user", "contact", "peer", "data"):
        inner = getattr(obj, attr, None)
        if inner is not None and inner is not obj:
            found = _extract_id(inner)
            if found:
                return found
    if isinstance(obj, dict):
        for key in ("id", "user_id", "chat_id"):
            v = obj.get(key)
            if isinstance(v, int):
                return v
        for key in ("user", "contact", "peer"):
            if isinstance(obj.get(key), dict):
                found = _extract_id(obj[key])
                if found:
                    return found
    return 0


class BaleUserAPI:
    """BotAPI-compatible façade over an aiobale *user* client."""

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
        self._db = db
        self._files: Dict[str, int] = {}          # file_id → access_hash
        self._dates: Dict[Tuple[int, int], int] = {}  # (chat, msg) → date
        self._chat_types: Dict[str, str] = {}
        self._chat_meta: Dict[str, dict] = {}
        self._id_cache: Dict[str, int] = {}
        self._handler: Optional[Callable[..., Any]] = None
        self._offset = 0
        self._started = False
        self.dp = Dispatcher()
        if client is not None:
            self.client = client
        else:
            kwargs: Dict[str, Any] = {"show_update_errors": True}
            if session_file is not None:
                kwargs["session_file"] = session_file
            if phone_number:
                kwargs["phone_number"] = phone_number
            if token:
                kwargs["token"] = token
            if user_agent:
                kwargs["user_agent"] = user_agent
            self.client = Client(self.dp, **kwargs)
        self._register_handlers()

    # ── plumbing ────────────────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        # ثبت aiobale به‌صورت decorator-factory است: dp.message()(handler)
        # (dp.message(handler) هندلر را «فیلتر» ثبت می‌کند — باگ زندهٔ تست‌شده!)
        self.dp.message()(self._on_message)
        self.dp.message_edited()(self._on_edited)
        self.dp.message_deleted()(self._on_deleted)

    def _bump(self) -> int:
        self._offset += 1
        return self._offset

    async def _emit(self, upd: dict) -> None:
        if self._handler is None:
            return
        try:
            await self._handler(upd, self._bump())
        except Exception:
            logger.exception("bale-user handler error")

    def _remember_date(self, chat_id: int, msg_id: int, date: Any) -> None:
        try:
            d = int(date or 0)
        except (TypeError, ValueError):
            d = 0
        self._dates[(int(chat_id), int(msg_id))] = d
        if self._db is not None and d:
            try:
                self._db.set_meta(f"bdate:{int(chat_id)}:{int(msg_id)}", str(d))
            except Exception:
                pass

    def _remember_file(self, file_id: Any, access_hash: Any) -> None:
        if file_id is None:
            return
        try:
            self._files[str(file_id)] = int(access_hash or 0)
        except (TypeError, ValueError):
            self._files[str(file_id)] = 0
        if self._db is not None:
            try:
                self._db.set_meta(f"bhash:{file_id}", str(int(access_hash or 0)))
            except Exception:
                pass

    def _date_for(self, chat_id: Any, msg_id: Any) -> int:
        d = self._dates.get((int(chat_id), int(msg_id)))
        if d is None and self._db is not None:
            try:
                raw = self._db.get_meta(f"bdate:{int(chat_id)}:{int(msg_id)}")
                d = int(raw) if raw else 0
                self._dates[(int(chat_id), int(msg_id))] = d
            except Exception:
                d = 0
        return int(d or 0)

    def _chat_type_of(self, chat_id: Any) -> str:
        return self._chat_types.get(str(chat_id), "group")

    def _ct_enum(self, chat_id: Any) -> Any:
        return _NAME_CHAT_TYPES.get(self._chat_type_of(chat_id), ChatType.GROUP)

    async def _ensure_chat_type(self, chat_id: Any) -> Any:
        key = str(chat_id)
        if key in self._chat_types:
            return _NAME_CHAT_TYPES.get(self._chat_types[key], ChatType.GROUP)
        try:
            full = await self.client.get_full_group(int(chat_id))
        except Exception:
            self._chat_types.setdefault(key, "private")
            return ChatType.PRIVATE
        gt = str(getattr(full, "group_type", "") or "").upper()
        name = "channel" if "CHANNEL" in gt else "group"
        self._chat_types[key] = name
        self._chat_meta.setdefault(key, {"id": int(chat_id), "type": name})
        self._chat_meta[key]["title"] = getattr(full, "title", None)
        uname = getattr(full, "username", None)
        if uname:
            self._chat_meta[key]["username"] = str(uname).lstrip("@")
        return _NAME_CHAT_TYPES[name]

    async def _resolve_id(self, chat_id: Any) -> int:
        if isinstance(chat_id, int):
            return chat_id
        key = str(chat_id).strip()
        if key.lstrip("-").isdigit():
            return int(key)
        if key in self._id_cache:
            return self._id_cache[key]
        found = await self.client.search_username(key.lstrip("@"))
        cid = _extract_id(found)
        if not cid:
            raise BotAPIError(f"chat not found: {chat_id!r}")
        self._id_cache[key] = cid
        return cid

    def _reply_ref(self, chat_id: Any, reply_to: Any) -> Any:
        if not reply_to:
            return None
        try:
            return InfoMessage(
                peer=Peer(type=_peer_type(self._chat_type_of(chat_id)), id=int(chat_id)),
                message_id=int(reply_to),
                date=self._date_for(chat_id, reply_to),
            )
        except Exception:
            return None

    def _result_for(self, chat_id: Any, msg: Any) -> dict:
        if isinstance(msg, list):
            msg = msg[-1] if msg else None
        if msg is None:
            return {"message_id": 0, "ok": True}
        mid = int(getattr(msg, "message_id", 0) or 0)
        self._remember_date(int(chat_id), mid, getattr(msg, "date", 0))
        return {"message_id": mid, "ok": True}

    # ── event handlers (aiobale → bridge updates) ───────────────────────────

    def normalize(self, msg: Any) -> dict:
        """Convert an aiobale ``Message`` into a Bot-API-like ``message`` dict."""
        chat_obj = getattr(msg, "chat", None) or getattr(msg, "peer", None)
        chat_id = int(getattr(chat_obj, "id", 0) or 0)
        ct = _chat_type_name(getattr(chat_obj, "type", None))
        self._chat_types[str(chat_id)] = ct
        meta = self._chat_meta.setdefault(str(chat_id), {"id": chat_id, "type": ct})
        out: dict = {
            "message_id": int(getattr(msg, "message_id", 0) or 0),
            "date": int(getattr(msg, "date", 0) or 0),
            "chat": dict(meta),
            "from": {"id": int(getattr(msg, "sender_id", 0) or 0), "is_bot": False},
        }
        self._remember_date(chat_id, out["message_id"], out["date"])

        text = getattr(msg, "text", None)
        if text is not None and not isinstance(text, str):
            text = getattr(text, "value", None) or getattr(text, "content", None)
        if text:
            out["text"] = text

        content = getattr(msg, "content", None)
        doc = getattr(content, "document", None) if content is not None else None
        if doc is not None:
            fid = getattr(doc, "file_id", None)
            self._remember_file(fid, getattr(doc, "access_hash", 0))
            fd = {
                "file_id": str(fid),
                "file_unique_id": str(fid),
                "file_name": _doc_name(doc) or None,
                "file_size": getattr(doc, "size", None),
                "mime_type": getattr(doc, "mime_type", None),
            }
            cap = getattr(doc, "caption", None)
            cap_text = getattr(cap, "content", None) if cap is not None else None
            if cap_text:
                out["caption"] = cap_text
            kind = _classify_document(doc)
            if kind == "photo":
                out["photo"] = [fd]
            elif kind == "animation":
                out["animation"] = fd
            else:
                out[kind] = fd

        replied = getattr(msg, "replied_to", None) or getattr(msg, "quoted_replied_to", None)
        rid = getattr(replied, "message_id", None) if replied is not None else None
        if rid:
            out["reply_to_message"] = {
                "message_id": int(rid),
                "chat": {"id": chat_id, "type": ct},
                "date": int(getattr(replied, "date", 0) or 0),
            }
        return out

    async def _on_message(self, msg: Any) -> None:
        await self._emit({"message": self.normalize(msg)})

    async def _on_edited(self, msg: Any) -> None:
        await self._emit({"edited_message": self.normalize(msg)})

    async def _on_deleted(self, selected: Union[SelectedMessages, Any]) -> None:
        if not selected or not getattr(selected, "ids", None):
            return
        peer = getattr(selected, "peer", None)
        chat_id = int(getattr(peer, "id", 0) or 0)
        ct = self._chat_types.get(str(chat_id))
        if ct is None:
            ct = "group" if _chat_type_name(getattr(peer, "type", 0)) == "group" else "private"
            self._chat_types[str(chat_id)] = ct
        await self._emit(
            {
                "deleted_messages": {
                    "chat": {"id": chat_id, "type": ct},
                    "message_ids": [int(i) for i in selected.ids],
                }
            }
        )

    # ── lifecycle ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """اتصال پس‌زمینه (start با run_in_background=True بلاک نمی‌کند)."""
        if self._started:
            return
        await self.client.start(run_in_background=True, signal_handling=False)
        self._started = True

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    async def listen(
        self,
        handler: Callable[..., Any],
        offset: int = 0,
        timeout: int = 30,
    ) -> None:
        self._handler = handler
        self._offset = int(offset or 0)
        await self.start()
        stop = asyncio.Event()
        try:
            await stop.wait()  # run until cancelled (gather is cancelled on stop)
        finally:
            try:
                await self.client.stop()
            except Exception:
                pass
            self._started = False

    async def close(self) -> None:
        try:
            await self.client.stop()
        except Exception:
            pass
        self._started = False

    # ── sending ─────────────────────────────────────────────────────────────

    async def send_chat_action(self, chat_id: Any, action: str = "typing") -> None:
        return None  # در API داخلی بله اندیکاتور «در حال تایپ» در دسترس نیست

    async def forward_message(self, chat_id: Any, from_chat_id: Any,
                             message_id: Any, **kw: Any) -> dict:
        raise BotAPIError("forward_message در حالت سلف‌بات پشتیبانی نمی‌شود")

    async def send_message(self, chat_id: Any, text: str, reply_to: Any = None, **kw: Any) -> dict:
        try:
            await self._ensure_started()
            cid = await self._resolve_id(chat_id)
            ct = await self._ensure_chat_type(cid)
            msg = await self.client.send_message(
                text=text,
                chat_id=cid,
                chat_type=ct,
                reply_to=self._reply_ref(cid, reply_to),
            )
            return self._result_for(cid, msg)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"send_message failed: {exc}") from exc

    async def _send_media(
        self,
        method_name: str,
        file: FileArg,
        chat_id: Any,
        caption: Optional[str] = None,
        reply_to: Any = None,
        file_kw: str = "file",
        **kw: Any,
    ) -> dict:
        try:
            await self._ensure_started()
            cid = await self._resolve_id(chat_id)
            ct = await self._ensure_chat_type(cid)
            method = getattr(self.client, method_name)
            msg = await method(
                **{
                    file_kw: file,
                    "chat_id": cid,
                    "chat_type": ct,
                    "caption": caption or None,
                    "reply_to": self._reply_ref(cid, reply_to),
                }
            )
            return self._result_for(cid, msg)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"{method_name} failed: {exc}") from exc

    async def send_photo(self, chat_id: Any, photo: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media(
            "send_photo", photo, chat_id, caption, reply_to, file_kw="photo")

    async def send_video(self, chat_id: Any, video: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media(
            "send_video", video, chat_id, caption, reply_to, file_kw="video")

    async def send_voice(self, chat_id: Any, voice: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media(
            "send_voice", voice, chat_id, caption, reply_to, file_kw="voice")

    async def send_audio(self, chat_id: Any, audio: FileArg, caption: Optional[str] = None,
                         reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media(
            "send_audio", audio, chat_id, caption, reply_to, file_kw="audio")

    async def send_document(self, chat_id: Any, document: FileArg, caption: Optional[str] = None,
                            reply_to: Any = None, **kw: Any) -> dict:
        return await self._send_media("send_document", document, chat_id, caption, reply_to)

    async def send_animation(self, chat_id: Any, animation: FileArg, caption: Optional[str] = None,
                             reply_to: Any = None, **kw: Any) -> dict:
        try:
            return await self._send_media(
                "send_gif", animation, chat_id, caption, reply_to, file_kw="gif")
        except BotAPIError:
            return await self._send_media("send_document", animation, chat_id, caption, reply_to)

    async def send_sticker(self, chat_id: Any, sticker: FileArg, reply_to: Any = None,
                           **kw: Any) -> dict:
        # send_sticker() انتظار شناسه استیکر دارد؛ فایل را به‌صورت سند می‌فرستیم.
        return await self._send_media("send_document", sticker, chat_id, None, reply_to)

    async def send_video_note(self, chat_id: Any, video_note: FileArg, reply_to: Any = None,
                              **kw: Any) -> dict:
        return await self._send_media(
            "send_video", video_note, chat_id, None, reply_to, file_kw="video")

    async def send_location(self, chat_id: Any, latitude: float, longitude: float,
                            reply_to: Any = None, **kw: Any) -> dict:
        link = f"https://maps.google.com/?q={latitude},{longitude}"
        return await self.send_message(chat_id, f"📍 {link}", reply_to=reply_to)

    async def send_venue(self, chat_id: Any, latitude: float, longitude: float, title: str,
                         address: str = "", reply_to: Any = None, **kw: Any) -> dict:
        link = f"https://maps.google.com/?q={latitude},{longitude}"
        return await self.send_message(chat_id, f"📍 {title}\n{address}\n{link}", reply_to=reply_to)

    async def send_contact(self, chat_id: Any, phone_number: str, first_name: str,
                           last_name: str = "", reply_to: Any = None, **kw: Any) -> dict:
        return await self.send_message(
            chat_id, f"👤 {first_name} {last_name}".strip() + f"\n{phone_number}", reply_to=reply_to
        )

    async def send_poll(self, chat_id: Any, question: str, options: List[str], **kw: Any) -> dict:
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

    # ── editing / deleting ──────────────────────────────────────────────────

    async def edit_message_text(self, chat_id: Any, message_id: Any, text: str, **kw: Any) -> dict:
        try:
            await self._ensure_started()
            cid = await self._resolve_id(chat_id)
            ct = await self._ensure_chat_type(cid)
            await self.client.edit_message(
                text=text, message_id=int(message_id), chat_id=cid, chat_type=ct)
            return {"ok": True, "message_id": int(message_id)}
        except Exception as exc:
            raise BotAPIError(f"edit_message failed: {exc}") from exc

    async def edit_message_caption(self, chat_id: Any, message_id: Any, caption: Optional[str],
                                   **kw: Any) -> dict:
        # RPC ویرایش، اسلات متن/کپشن را عوض می‌کند؛ ممکن است روی رسانه رد شود.
        return await self.edit_message_text(chat_id, message_id, caption or "", **kw)

    async def delete_message(self, chat_id: Any, message_id: Any) -> dict:
        try:
            await self._ensure_started()
            cid = await self._resolve_id(chat_id)
            ct = await self._ensure_chat_type(cid)
            date = self._date_for(cid, message_id)
            await self.client.delete_message(
                message_id=int(message_id),
                message_date=date,
                chat_id=cid,
                chat_type=ct,
            )
            return {"ok": True}
        except Exception as exc:
            raise BotAPIError(f"delete_message failed: {exc}") from exc

    # ── files / meta ────────────────────────────────────────────────────────

    def _access_hash_for(self, file_id: Any) -> Optional[int]:
        h = self._files.get(str(file_id))
        if h is None and self._db is not None:
            try:
                raw = self._db.get_meta(f"bhash:{file_id}")
                h = int(raw) if raw else None
                if h is not None:
                    self._files[str(file_id)] = h
            except Exception:
                h = None
        return h

    async def download_file(self, file_id: Any, dest: Union[str, Path],
                            **kw: Any) -> Union[str, Path]:
        h = self._access_hash_for(file_id)
        if h is None:
            raise BotAPIError(f"no access_hash cached for file {file_id!r}")
        try:
            await self._ensure_started()
            await self.client.download_file(
                file_id=int(file_id), access_hash=int(h), destination=str(dest), seek=True
            )
            return dest
        except Exception as exc:
            raise BotAPIError(f"download_file failed: {exc}") from exc

    async def get_file(self, file_id: Any, **kw: Any) -> dict:
        h = self._access_hash_for(file_id)
        if h is None:
            raise BotAPIError(f"no access_hash cached for file {file_id!r}")
        return {"file_id": str(file_id), "ok": True, "_access_hash": h}

    async def get_me(self) -> dict:
        try:
            await self._ensure_started()
            info = getattr(self.client, "me", None)
            if info is None:
                info = await self.client.get_me()
        except Exception as exc:
            raise BotAPIError(f"get_me failed: {exc}") from exc
        uid = int(getattr(info, "id", 0) or 0)
        user_obj = getattr(info, "user", None)  # ClientData.user → UserAuth
        name = _unwrap(getattr(user_obj, "name", None)) or getattr(info, "name", None)
        username = _unwrap(getattr(user_obj, "username", None)) or getattr(info, "username", None)
        if uid and (not name or not username):
            try:
                user = await self.client.load_user(uid, ChatType.PRIVATE)
                name = name or _unwrap(getattr(user, "name", None))
                username = username or _unwrap(getattr(user, "username", None))
            except Exception:
                pass
        return {
            "id": uid,
            "is_bot": False,
            "first_name": str(name or "Bale user"),
            "username": str(username).lstrip("@") if username else None,
        }

    async def get_chat(self, ref: Union[str, int]) -> dict:
        await self._ensure_started()
        try:
            cid = await self._resolve_id(ref)
        except BotAPIError:
            raise
        except Exception as exc:
            raise BotAPIError(f"get_chat failed for {ref!r}: {exc}") from exc
        out: dict = {"id": cid, "type": self._chat_types.get(str(cid))}
        try:
            full = await self.client.get_full_group(cid)
            gt = str(getattr(full, "group_type", "") or "").upper()
            name = "channel" if "CHANNEL" in gt else "group"
            self._chat_types[str(cid)] = name
            out["type"] = name
            out["title"] = _unwrap(getattr(full, "title", None))
            uname = _unwrap(getattr(full, "username", None))
            if uname:
                out["username"] = str(uname).lstrip("@")
        except Exception:
            try:
                user = await self.client.load_user(cid)
                self._chat_types[str(cid)] = "private"
                out["type"] = "private"
                out["title"] = _unwrap(getattr(user, "name", None))
                uname = _unwrap(getattr(user, "username", None))
                if uname:
                    out["username"] = str(uname).lstrip("@")
            except Exception:
                out.setdefault("type", out.get("type") or "private")
        self._chat_meta.setdefault(str(cid), {}).update({k: v for k, v in out.items() if v})
        self._chat_meta[str(cid)]["id"] = cid
        self._chat_meta[str(cid)]["type"] = out.get("type") or "private"
        return out
