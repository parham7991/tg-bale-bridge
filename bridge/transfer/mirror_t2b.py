"""T2BEngine — آینه‌سازی تلگرام → بله: متن، هر نوع رسانه، آلبوم، ریپلای، فوروارد.

همهٔ فالبک‌های ارسال (عکس→فایل، گیف→ویدیو→فایل، ویدیودایره‌ای→ویدیو→فایل، …)
و سقف‌های آپلود دقیقاً مثل قبل همین‌جاست.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .. import formatter as fmt
from ..bot_api import BotAPIError
from .types_map import GROUPABLE, fingerprint, tg_kind

logger = logging.getLogger("bridge.transfer.t2b")


class T2BEngine:
    """هر پیام تلگرامی را به هر جفتِ فعال در بله می‌رساند."""

    def __init__(self, tg, bale, db, cfg) -> None:
        self.tg = tg
        self.bale = bale
        self.db = db
        self.cfg = cfg

    # ───────────────────────────── ورودی ─────────────────────────────
    async def mirror(self, msgs) -> None:
        msgs = [m for m in msgs if not self.db.was_sent("tg", str(m.chat_id), m.id)]
        if not msgs:
            return
        pairs = self.db.pairs_for_tg(msgs[0].chat_id)
        if not pairs:
            return
        logger.info("تلگرام→بله: %d پیام از chat %s", len(msgs), msgs[0].chat_id)
        for pair in pairs:
            try:
                await self.pair_send(msgs, pair)
            except Exception:
                logger.exception("ارسال به بله ناموفق (pair #%s)", pair["id"])

    async def pair_send(self, msgs, pair) -> None:
        dst = pair["bale_chat_id"]
        first = msgs[0]
        reply_to = None
        if first.reply_to_msg_id:
            for o in self.db.other_side(
                    "tg", str(first.chat_id), first.reply_to_msg_id, pair["id"]):
                if o["platform"] == "bale":
                    reply_to = o["msg"]
                    break

        mapped: list = []
        if len(msgs) == 1:
            ids = await self.msg_to_bale(msgs[0], dst, reply_to)
            for did in ids:
                mapped.append((msgs[0], did))
        else:
            mapped = await self.album_to_bale(msgs, dst, reply_to)

        for src_msg, did in mapped:
            self.db.add_map(pair["id"], "tg", str(src_msg.chat_id), src_msg.id,
                            "bale", str(dst), did)
            self.db.mark_sent("bale", str(dst), did)
            self.db.add_fp("bale", str(dst),
                           fingerprint(tg_kind(src_msg), (src_msg.message or "")))

    # --------------------------------- ارسال یک پیام تلگرام به بله
    async def msg_to_bale(self, msg, dst, reply_to, preloaded=None, kind=None) -> list:
        """لیست شناسه‌های پیام ساخته‌شده در بله را برمی‌گرداند."""
        kind = kind or tg_kind(msg)
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
            geo = msg.media.geo
            if kind == "venue":
                await self.bale.send_location(dst, geo.lat, geo.long, reply_to)
                text = fmt.join_header(header, fmt.render_tg_venue(msg))
                m2 = await self.bale.send_message(
                    dst, fmt.truncate(text, self.cfg.LIMIT_TEXT))
                return [m2["message_id"]]
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
                m = await self.bale.send_message(
                    dst, "⚠️ دانلود رسانه از تلگرام ناموفق بود")
                return [m["message_id"]]
            size = Path(path).stat().st_size
            caption = fmt.truncate(
                fmt.join_header(header, body), self.cfg.LIMIT_CAPTION) or None
            if size > self.cfg.MAX_BALE_UPLOAD:
                note = (f"⚠️ فایل «{Path(path).name}» ({size // (1024*1024)}MB) "
                        f"بزرگ‌تر از سقف آپلود بله است و منتقل نشد.")
                m = await self.bale.send_message(dst, note, reply_to)
                return [m["message_id"]]
            m = await self.send_media(kind, dst, path, caption, reply_to, size)
            return [m["message_id"]]
        finally:
            if tmp and path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass

    # --------------------------------- فالبک‌های ارسال رسانه
    async def send_media(self, kind, dst, path, caption, reply_to, size):
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
                except BotAPIError as e:
                    logger.warning("sendPhoto failed (%s) — ارسال به‌صورت فایل", e)
            return await as_doc("⚠️ عکس به‌صورت فایل ارسال شد.")

        if kind == "video":
            try:
                return await b.send_video(dst, path, caption=caption, reply_to=reply_to)
            except BotAPIError:
                return await as_doc("⚠️ ویدیو به‌صورت فایل ارسال شد.")

        if kind == "animation":
            try:
                return await b.send_animation(dst, path, caption=caption, reply_to=reply_to)
            except BotAPIError:
                pass
            try:
                return await b.send_video(dst, path, caption=caption, reply_to=reply_to)
            except BotAPIError:
                return await as_doc("⚠️ گیف به‌صورت فایل ارسال شد.")

        if kind == "audio":
            try:
                return await b.send_audio(dst, path, caption=caption, reply_to=reply_to)
            except BotAPIError:
                return await as_doc()

        if kind == "voice":
            try:
                return await b.send_voice(dst, path, caption=caption, reply_to=reply_to)
            except BotAPIError:
                return await as_doc("⚠️ پیام صوتی به‌صورت فایل ارسال شد.")

        if kind == "sticker":
            try:
                return await b.send_sticker(dst, path, reply_to=reply_to)
            except BotAPIError:
                return await as_doc("⚠️ استیکر به‌صورت فایل ارسال شد.")

        if kind == "video_note":
            try:
                return await b.send_video_note(dst, path, reply_to=reply_to)
            except BotAPIError:
                pass
            try:
                return await b.send_video(dst, path, caption="🎥 ویدیوی دایره‌ای",
                                          reply_to=reply_to)
            except BotAPIError:
                return await as_doc("⚠️ ویدیوی دایره‌ای به‌صورت فایل ارسال شد.")

        return await as_doc()

    # --------------------------------- آلبوم تلگرام -> بله
    async def album_to_bale(self, msgs, dst, reply_to) -> list:
        prepared, others = [], []
        for m in msgs:
            kind = tg_kind(m)
            if kind in GROUPABLE:
                prepared.append((m, kind))
            else:
                others.append(m)

        results: list = []
        paths: list = []

        # دانلود موازی
        async def dl(m):
            p = await m.download_media(file=str(self.cfg.TMP_DIR))
            if p:
                paths.append(Path(p))
            return (m, tg_kind(m), p)

        downloaded = list(await asyncio.gather(*[dl(m) for m, _ in prepared])) \
            if prepared else []

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
            except (BotAPIError, ValueError, TypeError) as e:
                logger.warning("sendMediaGroup ناموفق (%s) — ارسال تکی", e)

        if not sent_ok:
            for m, kind, p, caption in group:
                try:
                    size = Path(p).stat().st_size
                    s = await self.send_media(kind, dst, p, caption or None,
                                              reply_to, size)
                    results.append((m, s["message_id"]))
                except Exception:
                    logger.exception("ارسال آیتم آلبوم ناموفق")
                    s = await self.bale.send_message(
                        dst, "⚠️ یکی از فایل‌های آلبوم منتقل نشد")
                    results.append((m, s["message_id"]))

        for m in others:
            results.extend(await self.msg_to_bale(m, dst, reply_to))

        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        results.sort(key=lambda t: t[0].id)
        return results

    async def _send_after_group(self, m, dst, p) -> list:
        if p:
            try:
                size = Path(p).stat().st_size
                header = await fmt.tg_forward_header(m, self.tg)
                caption = fmt.truncate(
                    fmt.join_header(header, fmt.tg_text_to_bale(m.message or "",
                                                                m.entities)),
                    self.cfg.LIMIT_CAPTION) or None
                s = await self.send_media(tg_kind(m), dst, p, caption, None, size)
                return [(m, s["message_id"])]
            finally:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        s = await self.bale.send_message(
            dst, "⚠️ یکی از فایل‌های آلبوم بزرگ‌تر از سقف بله بود")
        return [(m, s["message_id"])]
