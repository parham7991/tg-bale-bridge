"""نگاشت‌ها و کمک‌تابع‌های خالص موتور همگام‌سازی — بدون شبکه و بدون وضعیت.

کلاه‌بندی پیام تلگرام، استخراج محتوای پیام بله، ساخت موجودیت‌های تلگرام با
ریاضی آفست UTF-16 و اثر انگشت محتوا برای نگهبان لوپ.
"""
from __future__ import annotations

import hashlib
from typing import Any

from telethon import types as tg_t

# انواع رسانهٔ شناخته‌شده / انواع قابل گروه‌شدن در آلبوم
MEDIA_KINDS = ("photo", "video", "animation", "audio", "voice", "sticker", "document",
               "video_note", "contact", "location", "text")
GROUPABLE = ("photo", "video", "document", "audio")

# پسوند پیش‌فرض فایل موقت بر اساس نوع پیام بله
EXT_BY_KIND = {"photo": ".jpg", "video": ".mp4", "animation": ".mp4",
               "audio": ".mp3", "voice": ".ogg", "sticker": ".webp",
               "document": ""}


def fingerprint(kind: str, text: str) -> str:
    """اثر انگشت محتوا — برای تشخیص پژواک (loop) بله⇄تلگرام."""
    return hashlib.sha1(f"{kind}|{text or ''}".encode()).hexdigest()


# نام تاریخی — تست‌ها و شیم از همین استفاده می‌کنند
_fp = fingerprint


def tg_kind(msg: Any) -> str:
    """کلاه‌بندی پیام تلگرام به یکی از انواع شناخته‌شدهٔ پل."""
    media = msg.media
    if isinstance(media, tg_t.MessageMediaPoll):
        return "poll"
    if isinstance(media, tg_t.MessageMediaDice):
        return "dice"
    if isinstance(media, tg_t.MessageMediaContact):
        return "contact"
    if isinstance(media, tg_t.MessageMediaVenue):
        return "venue"
    if isinstance(media, (tg_t.MessageMediaGeo, tg_t.MessageMediaGeoLive)):
        return "location"
    if getattr(msg, "action", None) is not None:
        return "service"
    if msg.photo:
        return "photo"
    if msg.video:
        return "video"
    if msg.video_note:
        return "video_note"
    if msg.voice:
        return "voice"
    if msg.audio:
        return "audio"
    if msg.gif:
        return "animation"
    if msg.sticker:
        return "sticker"
    if msg.game:
        return "game"
    if msg.document:
        return "document"
    if msg.text or msg.message:
        return "text"
    return "unsupported"


def bale_content(m: dict) -> dict:
    """استخراج محتوای یکتا از پیام داخلی بله (دیکشنری Bot-API شکل)."""

    def fget(obj, *keys):
        for k in keys:
            if isinstance(obj, dict) and obj.get(k) is not None:
                return obj[k]
        return None

    text = m.get("text") or m.get("caption") or ""
    if m.get("photo"):
        sizes = m["photo"]
        best = sizes[-1] if sizes else {}
        return {"kind": "photo", "text": text, "file_id": best.get("file_id"),
                "file_name": "photo.jpg", "size": best.get("file_size"),
                "mime": "image/jpeg"}
    for kind, key in (("animation", "animation"), ("video", "video"), ("audio", "audio"),
                      ("voice", "voice"), ("sticker", "sticker"), ("document", "document")):
        if m.get(key):
            f = m[key]
            return {"kind": kind, "text": text, "file_id": f.get("file_id"),
                    "file_name": f.get("file_name"), "size": f.get("file_size"),
                    "mime": f.get("mime_type")}
    if m.get("contact"):
        c = m["contact"]
        return {"kind": "contact", "text": text,
                "phone_number": c.get("phone_number"), "first_name": c.get("first_name"),
                "last_name": c.get("last_name")}
    if m.get("location"):
        loc = m["location"]
        return {"kind": "location", "text": text,
                "latitude": loc.get("latitude"), "longitude": loc.get("longitude")}
    if m.get("text"):
        return {"kind": "text", "text": text}
    return {"kind": "unsupported", "text": text}


def build_entities(text: str, ents):
    """ساخت موجودیت‌های Telethon از (نوع، آفست، طول، url) با ریاضی UTF-16."""
    if not ents:
        return []
    p2u = {}
    u = 0
    for i, ch in enumerate(text):
        p2u[i] = u
        u += 2 if ord(ch) > 0xFFFF else 1
    p2u[len(text)] = u
    out = []
    for etype, off, length, url in ents:
        if off < 0 or off + length > len(text) or length <= 0:
            continue
        off_u = p2u.get(off, 0)
        len_u = p2u.get(off + length, u) - off_u
        if etype == "bold":
            out.append(tg_t.MessageEntityBold(offset=off_u, length=len_u))
        elif etype == "italic":
            out.append(tg_t.MessageEntityItalic(offset=off_u, length=len_u))
        elif etype == "text_link" and url:
            out.append(tg_t.MessageEntityTextUrl(offset=off_u, length=len_u, url=url))
    return out
