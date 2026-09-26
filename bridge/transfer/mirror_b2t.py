"""B2TEngine — آینه‌سازی بله → تلگرام: متن با موجودیت، رسانه، آلبوم، ریپلای.

سقف دانلود بله (۲۰MB)، نام‌گذاری فایل موقت، ارسال با caption_entities
(سازگار با نسخه‌های Telethon) و فالبک آلبوم تکی — همه دقیقاً مثل قبل.
"""
from __future__ import annotations

import logging
from pathlib import Path

from telethon import types as tg_t

from .. import formatter as fmt
from .types_map import EXT_BY_KIND, bale_content, build_entities, fingerprint

logger = logging.getLogger("bridge.transfer.b2t")


class B2TEngine:
    """هر پیام بله را به هر جفتِ فعال در تلگرام می‌رساند."""

    def __init__(self, tg, bale, db, cfg) -> None:
        self.tg = tg
        self.bale = bale
        self.db = db
        self.cfg = cfg

    # ───────────────────────────── ورودی ─────────────────────────────
    async def mirror(self, msgs) -> None:
        out = []
        for m in msgs:
            chat_key = str((m.get("chat") or {}).get("id"))
            if self.db.was_sent("bale", chat_key, m.get("message_id")):
                continue
            c = bale_content(m)
            if self.db.check_fp("bale", chat_key,
                                fingerprint(c["kind"], c["text"] or "")):
                continue
            out.append(m)
        if not out:
            return
        chat = out[0].get("chat") or {}
        pairs = self.db.pairs_for_bale(chat.get("id"), chat.get("username"))
        if not pairs:
            logger.debug("بله→تلگرام: جفتی برای chat %s نیست — نادیده گرفته شد",
                         chat.get("id"))
            return
        logger.info("بله→تلگرام: %d پیام از chat %s", len(out), chat.get("id"))
        for pair in pairs:
            try:
                await self.pair_send(out, pair)
            except Exception:
                logger.exception("ارسال به تلگرام ناموفق (pair #%s)", pair["id"])

    async def pair_send(self, msgs, pair) -> None:
        dst = int(pair["tg_chat_id"])
        first = msgs[0]
        reply_to = None
        rtm = first.get("reply_to_message")
        if rtm:
            for o in self.db.other_side("bale", str((first.get("chat") or {}).get("id")),
                                        rtm.get("message_id"), pair["id"]):
                if o["platform"] == "tg":
                    reply_to = o["msg"]
                    break

        mapped = []
        if len(msgs) == 1:
            res = await self.msg_to_tg(msgs[0], dst, reply_to)
            for tmsg in res:
                mapped.append((msgs[0], tmsg))
        else:
            mapped = await self.album_to_tg(msgs, dst, reply_to)

        for bm, tmsg in mapped:
            self.db.add_map(pair["id"], "bale", str((bm.get("chat") or {}).get("id")),
                            bm.get("message_id"), "tg", str(dst), tmsg.id)
            self.db.mark_sent("tg", str(dst), tmsg.id)
            c = bale_content(bm)
            self.db.add_fp("tg", str(dst), fingerprint(c["kind"], c["text"] or ""))

    # --------------------------------- ارسال یک پیام بله به تلگرام
    async def msg_to_tg(self, m, dst, reply_to) -> list:
        """محتوای بله را به تلگرام می‌فرستد؛ لیست پیام‌های ساخته‌شده را برمی‌گرداند."""
        c = bale_content(m)
        header = fmt.bale_forward_header(m)
        entity = await self.entity(dst)

        if c["kind"] in ("text", "unsupported"):
            plain, ents = fmt.bale_text_to_tg(c["text"] or "")
            full = fmt.join_header(header, plain)
            shift = len(header) + (1 if header else 0)
            if len(full) <= self.cfg.LIMIT_TEXT:
                tg_ents = build_entities(
                    full, [(t, o + shift, ln, u) for t, o, ln, u in ents])
                try:
                    msg = await self.tg.send_message(entity, full,
                                                     formatting_entities=tg_ents or None,
                                                     reply_to=reply_to)
                except TypeError:
                    msg = await self.tg.send_message(entity, full, reply_to=reply_to)
                return [msg]
            sent = []
            for i, chunk in enumerate(fmt.split_text(full, self.cfg.LIMIT_TEXT)):
                msg = await self.tg.send_message(entity, chunk,
                                                 reply_to=reply_to if i == 0 else None)
                sent.append(msg)
            return sent

        if c["kind"] == "contact":
            media = tg_t.InputMediaContact(
                phone_number=str(c.get("phone_number") or ""),
                first_name=c.get("first_name") or "",
                last_name=c.get("last_name") or "",
                user_id=0,
            )
            msg = await self.tg.send_file(entity, media, reply_to=reply_to)
            return [msg]

        if c["kind"] == "location":
            lat, lon = c.get("latitude"), c.get("longitude")
            media = tg_t.InputMediaGeoPoint(
                tg_t.InputGeoPoint(lat=float(lat), long=float(lon)))
            msg = await self.tg.send_file(entity, media, reply_to=reply_to)
            return [msg]

        # رسانه‌ها
        if c.get("size") and c["size"] > self.cfg.MAX_BALE_DOWNLOAD:
            mb = int(c["size"] / (1024 * 1024))
            note = (f"⚠️ فایل «{c.get('file_name') or c['kind']}» ({mb}MB) "
                    f"بزرگ‌تر از سقف دانلود بله (۲۰MB) است.")
            msg = await self.tg.send_message(entity, note, reply_to=reply_to)
            return [msg]

        path = await self.download(c)
        try:
            plain, ents = fmt.bale_text_to_tg(c["text"] or "")
            full = fmt.truncate(fmt.join_header(header, plain),
                                self.cfg.LIMIT_CAPTION) or ""
            shift = len(header) + (1 if header else 0)
            tg_ents = build_entities(
                full, [(t, o + shift, ln, u) for t, o, ln, u in ents])
            kwargs = dict(caption=full or None, reply_to=reply_to)
            if c["kind"] == "voice":
                kwargs["voice_note"] = True
            if c["kind"] == "document":
                kwargs["force_document"] = True
            if c["kind"] == "video":
                kwargs["supports_streaming"] = True
            msg = await self.send_file(entity, path,
                                       caption_entities=tg_ents or None, **kwargs)
            return [msg]
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

    # --------------------------------- آلبوم بله -> تلگرام
    async def album_to_tg(self, msgs, dst, reply_to) -> list:
        entity = await self.entity(dst)
        results = []
        files, caps, owners = [], [], []
        for m in msgs:
            c = bale_content(m)
            if c["kind"] in ("photo", "video", "audio", "document") and c.get("file_id") \
                    and (c.get("size") or 0) <= self.cfg.MAX_BALE_DOWNLOAD:
                path = await self.download(c)
                header = fmt.bale_forward_header(m) if m is msgs[0] else ""
                plain, ents = fmt.bale_text_to_tg(c["text"] or "")
                cap = fmt.truncate(fmt.join_header(header, plain),
                                   self.cfg.LIMIT_CAPTION_GROUP)
                files.append(path)
                caps.append(cap)
                owners.append(m)
            else:
                res = await self.msg_to_tg(m, dst, reply_to)
                for t in res:
                    results.append((m, t))

        if len(files) >= 2:
            try:
                sent = await self.tg.send_file(entity, files, caption=caps,
                                               reply_to=reply_to)
                if not isinstance(sent, list):
                    sent = [sent]
                for m, t in zip(owners, sent):
                    results.append((m, t))
            except Exception as e:
                logger.warning("ارسال آلبوم تلگرام ناموفق (%s) — ارسال تکی", e)
                for m, p, cap in zip(owners, files, caps):
                    t = await self.tg.send_file(entity, p, caption=cap or None,
                                                reply_to=reply_to)
                    results.append((m, t))
        elif files:
            for m, p, cap in zip(owners, files, caps):
                t = await self.tg.send_file(entity, p, caption=cap or None,
                                            reply_to=reply_to)
                results.append((m, t))

        for p in files:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        results.sort(key=lambda t: t[0].get("message_id", 0))
        return results

    # --------------------------------- کمک‌تابع‌های تلگرام
    async def entity(self, chat_id: int):
        try:
            return await self.tg.get_input_entity(int(chat_id))
        except Exception:
            return await self.tg.get_entity(int(chat_id))

    async def send_file(self, entity, path, **kwargs):
        """send_file با پشتیبانی caption_entities (سازگاری نسخه‌های مختلف Telethon)."""
        try:
            return await self.tg.send_file(entity, path, **kwargs)
        except TypeError:
            kwargs.pop("caption_entities", None)
            return await self.tg.send_file(entity, path, **kwargs)

    # --------------------------------- دانلود فایل بله
    async def download(self, c: dict):
        name = Path(str(c.get("file_name")
                        or f"{c['kind']}{EXT_BY_KIND.get(c['kind'], '')}")).name
        dest = self.cfg.TMP_DIR / f"bale_{str(c.get('file_id', 'f'))[-12:]}_{name}"
        await self.bale.download_file(c["file_id"], dest)
        return dest
