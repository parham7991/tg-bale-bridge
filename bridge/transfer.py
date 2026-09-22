"""موتور همگام‌سازی: تلگرام ⇄ بله (متن، رسانه، آلبوم، ویرایش، حذف)."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from telethon import types as tg_t

from . import formatter as fmt
from .bale_api import BaleAPI, BaleError

log = logging.getLogger("bridge")

MEDIA_KINDS = ("photo", "video", "animation", "audio", "voice", "sticker", "document",
               "video_note", "contact", "location", "text")
GROUPABLE = ("photo", "video", "document", "audio")


def _fp(kind: str, text: str) -> str:
    return hashlib.sha1(f"{kind}|{text or ''}".encode()).hexdigest()


class Bridge:
    def __init__(self, tg, bale: BaleAPI, db, cfg, my_tg_id: int, bale_bot: dict):
        self.tg = tg
        self.bale = bale
        self.db = db
        self.cfg = cfg
        self.my_tg_id = int(my_tg_id)
        self.bale_bot = bale_bot or {}
        self.q_tg: asyncio.Queue = asyncio.Queue()
        self.q_bale: asyncio.Queue = asyncio.Queue()
        self._albums_tg: dict = {}
        self._albums_bale: dict = {}
        self._album_tasks: dict = {}
        self._ignore_tg: set = set()   # (chat, msg) — حذف‌های خودمان
        self._ignore_bale: set = set()

    def workers(self):
        return [self._worker_tg(), self._worker_bale()]

    # ================================================================ صف‌ها
    async def _worker_tg(self):
        while True:
            job = await self.q_tg.get()
            try:
                await self._dispatch_tg(job)
            except Exception:
                log.exception("خطا در پردازش رویداد تلگرام")

    async def _worker_bale(self):
        while True:
            job = await self.q_bale.get()
            try:
                await self._dispatch_bale(job)
            except Exception:
                log.exception("خطا در پردازش رویداد بله")

    async def _dispatch_tg(self, job):
        kind, payload = job
        if kind == "new":
            await self._mirror_tg(payload)
        elif kind == "edit":
            await self._process_tg_edit(payload)
        elif kind == "delete":
            await self._process_tg_delete(payload[0], payload[1])

    async def _dispatch_bale(self, job):
        kind, payload = job
        if kind == "new":
            await self._mirror_bale(payload)
        elif kind == "edit":
            await self._process_bale_edit(payload)

    # ================================================================ رویدادهای تلگرام
    async def on_tg_new(self, msg):
        chat_key = str(msg.chat_id)
        if self.db.was_sent("tg", chat_key, msg.id):
            return
        if msg.grouped_id:
            key = (chat_key, msg.grouped_id)
            lst = self._albums_tg.setdefault(key, [])
            lst.append(msg)
            if len(lst) == 1:
                self._album_tasks[key] = asyncio.create_task(self._flush_tg_album(key))
            return
        await self.q_tg.put(("new", [msg]))

    async def _flush_tg_album(self, key):
        await asyncio.sleep(self.cfg.ALBUM_DELAY)
        msgs = self._albums_tg.pop(key, [])
        self._album_tasks.pop(key, None)
        if msgs:
            msgs.sort(key=lambda m: m.id)
            await self.q_tg.put(("new", msgs))

    async def on_tg_edit(self, msg):
        if self.db.was_sent("tg", str(msg.chat_id), msg.id):
            return
        await self.q_tg.put(("edit", msg))

    async def on_tg_delete(self, chat_id, deleted_ids):
        chat_key = str(chat_id)
        ids = []
        for mid in deleted_ids:
            if (chat_key, int(mid)) in self._ignore_tg:
                self._ignore_tg.discard((chat_key, int(mid)))
                continue
            ids.append(int(mid))
        if ids:
            await self.q_tg.put(("delete", (chat_key, ids)))

    # ================================================================ رویدادهای بله
    async def queue_bale_msg(self, m: dict):
        chat_key = str((m.get("chat") or {}).get("id"))
        if self.db.was_sent("bale", chat_key, m.get("message_id")):
            return
        gid = m.get("media_group_id")
        if gid:
            key = (chat_key, gid)
            lst = self._albums_bale.setdefault(key, [])
            lst.append(m)
            if len(lst) == 1:
                self._album_tasks[key] = asyncio.create_task(self._flush_bale_album(key))
            return
        await self.q_bale.put(("new", [m]))

    async def _flush_bale_album(self, key):
        await asyncio.sleep(self.cfg.ALBUM_DELAY * 1.4)
        msgs = self._albums_bale.pop(key, [])
        self._album_tasks.pop(key, None)
        if msgs:
            msgs.sort(key=lambda x: x.get("message_id", 0))
            await self.q_bale.put(("new", msgs))

    async def queue_bale_edit(self, m: dict):
        await self.q_bale.put(("edit", m))

    # ================================================================ تلگرام -> بله
    async def _mirror_tg(self, msgs):
        msgs = [m for m in msgs if not self.db.was_sent("tg", str(m.chat_id), m.id)]
        if not msgs:
            return
        pairs = self.db.pairs_for_tg(msgs[0].chat_id)
        if not pairs:
            return
        log.info("تلگرام→بله: %d پیام از chat %s", len(msgs), msgs[0].chat_id)
        for pair in pairs:
            try:
                await self._tg_to_bale_pair(msgs, pair)
            except Exception:
                log.exception("ارسال به بله ناموفق (pair #%s)", pair["id"])

    async def _tg_to_bale_pair(self, msgs, pair):
        dst = pair["bale_chat_id"]
        first = msgs[0]
        reply_to = None
        if first.reply_to_msg_id:
            for o in self.db.other_side(
                    "tg", str(first.chat_id), first.reply_to_msg_id, pair["id"]):
                if o["platform"] == "bale":
                    reply_to = o["msg"]
                    break

        mapped: list[tuple] = []
        if len(msgs) == 1:
            ids = await self._tg_msg_to_bale(msgs[0], dst, reply_to)
            for did in ids:
                mapped.append((msgs[0], did))
        else:
            mapped = await self._tg_album_to_bale(msgs, dst, reply_to)

        for src_msg, did in mapped:
            self.db.add_map(pair["id"], "tg", str(src_msg.chat_id), src_msg.id,
                            "bale", str(dst), did)
            self.db.mark_sent("bale", str(dst), did)
            self.db.add_fp("bale", str(dst),
                           _fp(self._tg_kind(src_msg), (src_msg.message or "")))

    # --------------------------------- ارسال یک پیام تلگرام به بله
    async def _tg_msg_to_bale(self, msg, dst, reply_to, preloaded=None, kind=None):
        """لیست شناسه‌های پیام ساخته‌شده در بله را برمی‌گرداند."""
        kind = kind or self._tg_kind(msg)
        header = await fmt.tg_forward_header(msg, self.tg)
        body = fmt.tg_text_to_bale(msg.message or "", msg.entities)

        if kind in ("text", "poll", "dice", "service", "unsupported", "game"):
            text = body
            if kind == "poll":
                text = fmt.render_tg_poll(msg)
            elif kind == "dice":
                text = fmt.render_tg_dice(msg)
            elif kind == "service":
                text = fmt.render_tg_service(msg)
            elif kind == "game":
                text = f"🎮 بازی: {body}" if body else "🎮 بازی تلگرام"
            elif kind == "unsupported":
                text = fmt.render_unsupported_tg(msg)
            full = fmt.join_header(header, text)
            sent_ids = []
            for i, chunk in enumerate(fmt.split_text(full, self.cfg.LIMIT_TEXT)):
                m = await self.bale.send_message(dst, chunk, reply_to if i == 0 else None)
                sent_ids.append(m["message_id"])
            return sent_ids

        if kind == "contact":
            c = msg.media
            m = await self.bale.send_contact(
                dst, c.phone_number, c.first_name or "", c.last_name or "", reply_to)
            return [m["message_id"]]

        if kind in ("location", "venue"):
            if kind == "venue":
                geo = msg.media.geo
                await self.bale.send_location(dst, geo.lat, geo.long, reply_to)
                text = fmt.join_header(header, fmt.render_tg_venue(msg))
                m2 = await self.bale.send_message(dst, fmt.truncate(text, self.cfg.LIMIT_TEXT))
                return [m2["message_id"]]
            geo = msg.media.geo
            m = await self.bale.send_location(dst, geo.lat, geo.long, reply_to)
            return [m["message_id"]]

        # رسانه‌ها
        path = preloaded
        tmp = False
        try:
            if path is None:
                path = await msg.download_media(file=str(self.cfg.TMP_DIR))
                tmp = True
            if not path:
                m = await self.bale.send_message(dst, "⚠️ دانلود رسانه از تلگرام ناموفق بود")
                return [m["message_id"]]
            size = Path(path).stat().st_size
            caption = fmt.truncate(fmt.join_header(header, body), self.cfg.LIMIT_CAPTION) or None
            if size > self.cfg.MAX_BALE_UPLOAD:
                note = (f"⚠️ فایل «{Path(path).name}» ({size // (1024*1024)}MB) "
                        f"بزرگ‌تر از سقف آپلود بله است و منتقل نشد.")
                m = await self.bale.send_message(dst, note, reply_to)
                return [m["message_id"]]
            m = await self._bale_send_media(kind, dst, path, caption, reply_to, size)
            return [m["message_id"]]
        finally:
            if tmp and path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass

    async def _bale_send_media(self, kind, dst, path, caption, reply_to, size):
        b = self.bale

        async def as_doc(note=None):
            cap = caption
            if note:
                cap = fmt.truncate(fmt.join_header(note, caption or ""),
                                   self.cfg.LIMIT_CAPTION) or None
            return await b.send_document(dst, path, caption=cap, reply_to=reply_to)

        if kind == "photo":
            if size <= self.cfg.MAX_BALE_PHOTO:
                try:
                    return await b.send_photo(dst, path, caption=caption, reply_to=reply_to)
                except BaleError as e:
                    log.warning("sendPhoto failed (%s) — ارسال به‌صورت فایل", e)
            return await as_doc("⚠️ عکس به‌صورت فایل ارسال شد.")

        if kind == "video":
            try:
                return await b.send_video(dst, path, caption=caption, reply_to=reply_to)
            except BaleError:
                return await as_doc("⚠️ ویدیو به‌صورت فایل ارسال شد.")

        if kind == "animation":
            try:
                return await b.send_animation(dst, path, caption=caption, reply_to=reply_to)
            except BaleError:
                pass
            try:
                return await b.send_video(dst, path, caption=caption, reply_to=reply_to)
            except BaleError:
                return await as_doc("⚠️ گیف به‌صورت فایل ارسال شد.")

        if kind == "audio":
            try:
                return await b.send_audio(dst, path, caption=caption, reply_to=reply_to)
            except BaleError:
                return await as_doc()

        if kind == "voice":
            try:
                return await b.send_voice(dst, path, caption=caption, reply_to=reply_to)
            except BaleError:
                return await as_doc("⚠️ پیام صوتی به‌صورت فایل ارسال شد.")

        if kind == "sticker":
            try:
                return await b.send_sticker(dst, path, reply_to=reply_to)
            except BaleError:
                return await as_doc("⚠️ استیکر به‌صورت فایل ارسال شد.")

        if kind == "video_note":
            try:
                return await b.send_video_note(dst, path, reply_to=reply_to)
            except BaleError:
                pass
            try:
                return await b.send_video(dst, path, caption="🎥 ویدیوی دایره‌ای",
                                          reply_to=reply_to)
            except BaleError:
                return await as_doc("⚠️ ویدیوی دایره‌ای به‌صورت فایل ارسال شد.")

        return await as_doc()

    # --------------------------------- آلبوم تلگرام -> بله
    async def _tg_album_to_bale(self, msgs, dst, reply_to):
        prepared, others = [], []
        for m in msgs:
            kind = self._tg_kind(m)
            if kind in GROUPABLE:
                prepared.append((m, kind))
            else:
                others.append(m)

        results: list[tuple] = []
        paths: list[Path] = []

        # دانلود موازی
        async def dl(m):
            p = await m.download_media(file=str(self.cfg.TMP_DIR))
            if p:
                paths.append(Path(p))
            return (m, self._tg_kind(m), p)

        downloaded = list(await asyncio.gather(*[dl(m) for m, _ in prepared])) if prepared else []

        group = []
        for m, kind, p in downloaded:
            if not p or Path(p).stat().st_size > self.cfg.MAX_BALE_UPLOAD:
                results.extend(await self._send_after_group(m, dst, p))
                continue
            caption = ""
            if m.message:
                header = await fmt.tg_forward_header(m, self.tg)
                caption = fmt.join_header(
                    header,
                    fmt.tg_text_to_bale(m.message, m.entities),
                )[: self.cfg.LIMIT_CAPTION_GROUP]
            group.append((m, kind, p, caption))

        sent_ok = False
        if len(group) >= 2:
            try:
                sent = await self.bale.send_media_group(
                    dst, [(k, p, c) for _, k, p, c in group], reply_to)
                for (m, _k, _p, _c), s in zip(group, sent):
                    results.append((m, s["message_id"]))
                sent_ok = True
            except (BaleError, ValueError, TypeError) as e:
                log.warning("sendMediaGroup ناموفق (%s) — ارسال تکی", e)

        if not sent_ok:
            for m, kind, p, caption in group:
                try:
                    size = Path(p).stat().st_size
                    s = await self._bale_send_media(kind, dst, p, caption or None, reply_to, size)
                    results.append((m, s["message_id"]))
                except Exception:
                    log.exception("ارسال آیتم آلبوم ناموفق")
                    s = await self.bale.send_message(dst, "⚠️ یکی از فایل‌های آلبوم منتقل نشد")
                    results.append((m, s["message_id"]))

        for m in others:
            results.extend(await self._tg_msg_to_bale(m, dst, reply_to))

        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        results.sort(key=lambda t: t[0].id)
        return results

    async def _send_after_group(self, m, dst, p):
        if p:
            try:
                size = Path(p).stat().st_size
                header = await fmt.tg_forward_header(m, self.tg)
                caption = fmt.truncate(
                    fmt.join_header(header, fmt.tg_text_to_bale(m.message or "", m.entities)),
                    self.cfg.LIMIT_CAPTION) or None
                s = await self._bale_send_media(self._tg_kind(m), dst, p, caption, None, size)
                return [(m, s["message_id"])]
            finally:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        s = await self.bale.send_message(dst, "⚠️ یکی از فایل‌های آلبوم بزرگ‌تر از سقف بله بود")
        return [(m, s["message_id"])]

    # --------------------------------- نوع پیام تلگرام
    @staticmethod
    def _tg_kind(msg) -> str:
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

    # ================================================================ بله -> تلگرام
    async def _mirror_bale(self, msgs):
        out = []
        for m in msgs:
            chat_key = str((m.get("chat") or {}).get("id"))
            if self.db.was_sent("bale", chat_key, m.get("message_id")):
                continue
            c = self._bale_content(m)
            if self.db.check_fp("bale", chat_key, _fp(c["kind"], c["text"] or "")):
                continue
            out.append(m)
        if not out:
            return
        chat = out[0].get("chat") or {}
        pairs = self.db.pairs_for_bale(chat.get("id"), chat.get("username"))
        if not pairs:
            return
        log.info("بله→تلگرام: %d پیام از chat %s", len(out), chat.get("id"))
        for pair in pairs:
            try:
                await self._bale_to_tg_pair(out, pair)
            except Exception:
                log.exception("ارسال به تلگرام ناموفق (pair #%s)", pair["id"])

    async def _bale_to_tg_pair(self, msgs, pair):
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
            res = await self._bale_msg_to_tg(msgs[0], dst, reply_to)
            for tmsg in res:
                mapped.append((msgs[0], tmsg))
        else:
            mapped = await self._bale_album_to_tg(msgs, dst, reply_to)

        for bm, tmsg in mapped:
            self.db.add_map(pair["id"], "bale", str((bm.get("chat") or {}).get("id")),
                            bm.get("message_id"), "tg", str(dst), tmsg.id)
            self.db.mark_sent("tg", str(dst), tmsg.id)
            c = self._bale_content(bm)
            self.db.add_fp("tg", str(dst), _fp(c["kind"], c["text"] or ""))

    async def _bale_msg_to_tg(self, m, dst, reply_to):
        """محتوای بله را به تلگرام می‌فرستد؛ لیست پیام‌های ساخته‌شده را برمی‌گرداند."""
        c = self._bale_content(m)
        header = fmt.bale_forward_header(m)
        entity = await self._tg_entity(dst)

        if c["kind"] in ("text", "unsupported"):
            plain, ents = fmt.bale_text_to_tg(c["text"] or "")
            full = fmt.join_header(header, plain)
            shift = len(header) + (1 if header else 0)
            if len(full) <= self.cfg.LIMIT_TEXT:
                tg_ents = self._build_entities(
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
            media = tg_t.InputMediaGeoPoint(tg_t.InputGeoPoint(lat=float(lat), long=float(lon)))
            msg = await self.tg.send_file(entity, media, reply_to=reply_to)
            return [msg]

        # رسانه‌ها
        if c.get("size") and c["size"] > self.cfg.MAX_BALE_DOWNLOAD:
            mb = int(c["size"] / (1024 * 1024))
            note = (f"⚠️ فایل «{c.get('file_name') or c['kind']}» ({mb}MB) "
                    f"بزرگ‌تر از سقف دانلود بله (۲۰MB) است.")
            msg = await self.tg.send_message(entity, note, reply_to=reply_to)
            return [msg]

        path = await self._download_bale_file(c)
        try:
            plain, ents = fmt.bale_text_to_tg(c["text"] or "")
            full = fmt.truncate(fmt.join_header(header, plain), self.cfg.LIMIT_CAPTION) or ""
            shift = len(header) + (1 if header else 0)
            tg_ents = self._build_entities(
                full, [(t, o + shift, ln, u) for t, o, ln, u in ents])
            kwargs = dict(caption=full or None, reply_to=reply_to)
            if c["kind"] == "voice":
                kwargs["voice_note"] = True
            if c["kind"] == "document":
                kwargs["force_document"] = True
            if c["kind"] == "video":
                kwargs["supports_streaming"] = True
            msg = await self._tg_send_file(entity, path, caption_entities=tg_ents or None, **kwargs)
            return [msg]
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

    async def _bale_album_to_tg(self, msgs, dst, reply_to):
        entity = await self._tg_entity(dst)
        results = []
        files, caps, owners = [], [], []
        for m in msgs:
            c = self._bale_content(m)
            if c["kind"] in ("photo", "video", "audio", "document") and c.get("file_id") \
                    and (c.get("size") or 0) <= self.cfg.MAX_BALE_DOWNLOAD:
                path = await self._download_bale_file(c)
                header = fmt.bale_forward_header(m) if m is msgs[0] else ""
                plain, ents = fmt.bale_text_to_tg(c["text"] or "")
                cap = fmt.truncate(fmt.join_header(header, plain),
                                   self.cfg.LIMIT_CAPTION_GROUP)
                files.append(path)
                caps.append(cap)
                owners.append(m)
            else:
                res = await self._bale_msg_to_tg(m, dst, reply_to)
                for t in res:
                    results.append((m, t))

        if len(files) >= 2:
            try:
                sent = await self.tg.send_file(entity, files, caption=caps, reply_to=reply_to)
                if not isinstance(sent, list):
                    sent = [sent]
                for m, t in zip(owners, sent):
                    results.append((m, t))
            except Exception as e:
                log.warning("ارسال آلبوم تلگرام ناموفق (%s) — ارسال تکی", e)
                for m, p, cap in zip(owners, files, caps):
                    t = await self.tg.send_file(entity, p, caption=cap or None,
                                                reply_to=reply_to)
                    results.append((m, t))
        elif files:
            for m, p, cap in zip(owners, files, caps):
                t = await self.tg.send_file(entity, p, caption=cap or None, reply_to=reply_to)
                results.append((m, t))

        for p in files:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        results.sort(key=lambda t: t[0].get("message_id", 0))
        return results

    async def _tg_entity(self, chat_id: int):
        try:
            return await self.tg.get_input_entity(int(chat_id))
        except Exception:
            return await self.tg.get_entity(int(chat_id))

    async def _tg_send_file(self, entity, path, **kwargs):
        """send_file با پشتیبانی caption_entities (سازگاری نسخه‌های مختلف Telethon)."""
        try:
            return await self.tg.send_file(entity, path, **kwargs)
        except TypeError:
            kwargs.pop("caption_entities", None)
            return await self.tg.send_file(entity, path, **kwargs)

    @staticmethod
    def _build_entities(text: str, ents):
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

    # --------------------------------- محتوای پیام بله
    @staticmethod
    def _bale_content(m: dict) -> dict:
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

    async def _download_bale_file(self, c: dict):
        ext_by_kind = {"photo": ".jpg", "video": ".mp4", "animation": ".mp4",
                       "audio": ".mp3", "voice": ".ogg", "sticker": ".webp",
                       "document": ""}
        name = Path(str(c.get("file_name") or f"{c['kind']}{ext_by_kind.get(c['kind'], '')}")).name
        dest = self.cfg.TMP_DIR / f"bale_{str(c.get('file_id', 'f'))[-12:]}_{name}"
        await self.bale.download_file(c["file_id"], dest)
        return dest

    # ================================================================ ویرایش
    async def _process_tg_edit(self, msg):
        chat_key = str(msg.chat_id)
        for o in self.db.other_side("tg", chat_key, msg.id):
            if o["platform"] != "bale":
                continue
            pair = self.db.get_pair(o["pair_id"])
            if not pair or pair["mode"] == "bale2tg":
                continue
            body = fmt.truncate(
                fmt.tg_text_to_bale(msg.message or "", msg.entities), self.cfg.LIMIT_TEXT)
            try:
                if self._tg_kind(msg) in ("text",):
                    await self.bale.edit_message_text(o["chat"], o["msg"], body)
                else:
                    await self.bale.edit_message_caption(o["chat"], o["msg"], body)
            except BaleError as e:
                log.warning("ویرایش در بله ناموفق (%s) — جایگزینی پیام", e)
                try:
                    await self.bale.delete_message(o["chat"], o["msg"])
                    ids = await self._tg_msg_to_bale(msg, pair["bale_chat_id"], None)
                    if ids:
                        self.db.replace_map_dst(o["row_id"], "bale", str(o["chat"]), ids[0])
                        self.db.mark_sent("bale", str(o["chat"]), ids[0])
                except Exception:
                    log.exception("جایگزینی پیام ویرایش‌شده ناموفق")

    async def _process_bale_edit(self, m: dict):
        chat_key = str((m.get("chat") or {}).get("id"))
        c = self._bale_content(m)
        for o in self.db.other_side("bale", chat_key, m.get("message_id")):
            if o["platform"] != "tg":
                continue
            pair = self.db.get_pair(o["pair_id"])
            if not pair or pair["mode"] == "tg2bale":
                continue
            try:
                entity = await self._tg_entity(int(o["chat"]))
                tmsg = await self.tg.get_messages(entity, ids=int(o["msg"]))
                if not tmsg:
                    continue
                plain, ents = fmt.bale_text_to_tg(c["text"] or "")
                tg_ents = self._build_entities(plain, ents)
                try:
                    await tmsg.edit(plain, formatting_entities=tg_ents or None)
                except TypeError:
                    await tmsg.edit(plain)
            except Exception as e:
                log.warning("ویرایش در تلگرام ناموفق (%s) — جایگزینی پیام", e)
                try:
                    self._ignore_tg.add((str(o["chat"]), int(o["msg"])))
                    await self.tg.delete_messages(int(o["chat"]), [int(o["msg"])])
                    res = await self._bale_msg_to_tg(m, int(o["chat"]), None)
                    if res:
                        self.db.replace_map_dst(o["row_id"], "tg", str(o["chat"]), res[0].id)
                        self.db.mark_sent("tg", str(o["chat"]), res[0].id)
                except Exception:
                    log.exception("جایگزینی پیام ویرایش‌شده ناموفق")

    # ================================================================ حذف
    async def _process_tg_delete(self, chat_key, ids):
        for mid in ids:
            for o in self.db.other_side("tg", chat_key, mid):
                if o["platform"] != "bale":
                    continue
                pair = self.db.get_pair(o["pair_id"])
                if not pair or pair["mode"] == "bale2tg":
                    continue
                try:
                    await self.bale.delete_message(o["chat"], o["msg"])
                except BaleError as e:
                    log.warning("حذف در بله ناموفق: %s", e)
                self.db.remove_map_row(o["row_id"])
