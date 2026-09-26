"""NormalizeEngine — تبدیل پیام داخلی aiobale به دیکشنری Bot-API (خالص + کش)."""
from __future__ import annotations

import logging
from typing import Any

from .session import BaleSession
from .types_map import (
    AMBIGUOUS_GROUP,
    chat_type_name,
    classify_document,
    doc_name,
    group_like_type_value,
)

logger = logging.getLogger("bridge.bale.normalize")


class NormalizeEngine:
    def __init__(self, session: BaleSession) -> None:
        self.s = session

    def normalize(self, msg: Any) -> dict:
        """``aiobale.types.Message`` → ``{"message_id","date","chat","from","text"|"photo"|…}``"""
        chat_obj = getattr(msg, "chat", None) or getattr(msg, "peer", None)
        chat_id = int(getattr(chat_obj, "id", 0) or 0)
        raw_type = getattr(chat_obj, "type", None)
        ct = chat_type_name(raw_type)
        # کانال‌ها در آپدیت بله گاهی نوع group-like می‌گیرند (ChatType.GROUP یا
        # PeerType.GROUP) — هرگز «group» مبهم را به کش ارسالها تزریق نکن؛
        # نشان «group?» می‌گذاریم تا ensure_chat_type با get_full_group قطعی‌اش کند.
        from_peer = getattr(msg, "chat", None) is None
        ambiguous = group_like_type_value(raw_type, peer_types=from_peer)
        self.s.chat_types.setdefault(
            str(chat_id), AMBIGUOUS_GROUP if ambiguous else ct)
        if not ambiguous:
            self.s.chat_types[str(chat_id)] = ct
        meta = self.s.chat_meta.setdefault(str(chat_id), {"id": chat_id, "type": ct})
        out: dict = {
            "message_id": int(getattr(msg, "message_id", 0) or 0),
            "date": int(getattr(msg, "date", 0) or 0),
            "chat": dict(meta),
            "from": {"id": int(getattr(msg, "sender_id", 0) or 0), "is_bot": False},
        }
        self.s.remember_date(chat_id, out["message_id"], out["date"])

        # متن (مستقیم یا داخل wrapper)
        text = getattr(msg, "text", None)
        if text is not None and not isinstance(text, str):
            text = getattr(text, "value", None) or getattr(text, "content", None)
        if text:
            out["text"] = text

        # رسانهٔ یکپارچه (DocumentMessage) → طبقه‌بندی با mime
        content = getattr(msg, "content", None)
        doc = getattr(content, "document", None) if content is not None else None
        if doc is not None:
            fid = getattr(doc, "file_id", None)
            self.s.remember_file(fid, getattr(doc, "access_hash", 0))
            fd = {
                "file_id": str(fid),
                "file_unique_id": str(fid),
                "file_name": doc_name(doc) or None,
                "file_size": getattr(doc, "size", None),
                "mime_type": getattr(doc, "mime_type", None),
            }
            cap = getattr(doc, "caption", None)
            cap_text = getattr(cap, "content", None) if cap is not None else None
            if cap_text:
                out["caption"] = cap_text
            kind = classify_document(doc)
            if kind == "photo":
                out["photo"] = [fd]
            elif kind == "animation":
                out["animation"] = fd
            else:
                out[kind] = fd

        # ریپلای
        replied = getattr(msg, "replied_to", None) or getattr(msg, "quoted_replied_to", None)
        rid = getattr(replied, "message_id", None) if replied is not None else None
        if rid:
            out["reply_to_message"] = {
                "message_id": int(rid),
                "chat": {"id": chat_id, "type": ct},
                "date": int(getattr(replied, "date", 0) or 0),
            }
        return out
