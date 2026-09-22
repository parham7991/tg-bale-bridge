"""نقطه شروع پل همگام‌سازی تلگرام ⇄ بله."""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from telethon import TelegramClient

import config as cfg
from bridge import logbuf
from bridge.admin import Admin
from bridge.bot_api import BotAPI, BotAPIError
from bridge.db import DB
from bridge.tg_bot import TgAdminBot
from bridge.tg_user import register as register_tg
from bridge.transfer import Bridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logging.getLogger("telethon").setLevel(logging.WARNING)
log = logging.getLogger("main")

BANNER = """
╔══════════════════════════════════════════╗
║   پل همگام‌سازی  تلگرام ⇄  بله            ║
╚══════════════════════════════════════════╝
"""


async def main():
    print(BANNER)
    started_at = time.time()
    log_handler = logbuf.install()

    problems = cfg.validate()
    if problems:
        for p in problems:
            log.error("پیکربندی: %s", p)
        sys.exit(1)

    db = DB(cfg.DB_PATH)
    if cfg.BALE_MODE == "user":
        from bridge.bale_user import BaleUserAPI

        bale = BaleUserAPI(
            session_file=cfg.BALE_SESSION, phone_number=cfg.BALE_PHONE or None, db=db)
        log.info("حالت بله: سلف‌بات (حساب کاربری) با aiobale — بدون نیاز به اد کردن ربات")
    else:
        bale = BotAPI(cfg.BALE_TOKEN, cfg.BALE_API_BASE)

    try:
        bale_me = await bale.get_me()
    except BotAPIError as e:
        log.error("اتصال به بله ناموفق — توکن/نشست را بررسی کنید: %s", e)
        sys.exit(1)
    label = "حساب بله (سلف)" if cfg.BALE_MODE == "user" else "ربات بله"
    log.info("%s: @%s (id=%s)", label, bale_me.get("username"), bale_me.get("id"))

    if cfg.BALE_MODE == "user" and not cfg.ADMIN_BALE_ID:
        # پنل ادمین بله بدون هیچ تنظیمی: در بله به خودتان پیام بدهید (ذخیره‌ها/خودچت)
        cfg.ADMIN_BALE_ID = int(bale_me.get("id") or 0)
        log.info("ADMIN_BALE_ID خودکار = %s (خودتان) — در بله به خودتان /help بدهید",
                 cfg.ADMIN_BALE_ID)

    tg = TelegramClient(str(cfg.SESSION_PATH), cfg.TG_API_ID, cfg.TG_API_HASH)
    await tg.start(phone=cfg.TG_PHONE or None)
    me = await tg.get_me()
    log.info("حساب تلگرام (سلف): %s (id=%s)", me.username or me.first_name, me.id)

    bridge = Bridge(tg, bale, db, cfg, me.id, bale_me)
    bridge.paused = db.get_meta("paused") == "1"
    if bridge.paused:
        log.warning("⏸ همگام‌سازی از قبل متوقف است (با /resume روشن کنید)")

    admin = Admin(db, bale, tg, bridge, cfg,
                  log_buffer=log_handler, started_at=started_at)
    register_tg(tg, bridge, admin, me.id)

    if not cfg.ADMIN_BALE_ID and cfg.BALE_MODE == "bot":
        log.warning("ADMIN_BALE_ID تنظیم نشده — در ربات بله /start بزنید")

    pairs = db.list_pairs()
    log.info("%d جفت کانال فعال است", len(pairs))

    # ---------- بات مدیریت تلگرام (اختیاری) ----------
    tg_bot_task = None
    tg_bot_api = None
    if cfg.TG_BOT_TOKEN:
        tg_bot_api = BotAPI(cfg.TG_BOT_TOKEN, cfg.TG_BOT_API_BASE)
        try:
            tg_bot_api.me = await tg_bot_api.get_me()
        except BotAPIError as e:
            log.error("بات مدیریت تلگرام ناموفق — TG_BOT_TOKEN را بررسی کنید: %s", e)
            tg_bot_api = None
        if tg_bot_api:
            admin.tg_bot_info = tg_bot_api.me
            tgbot = TgAdminBot(tg_bot_api, admin, db, cfg)
            tg_bot_task = asyncio.create_task(tgbot.start())
    else:
        log.info("TG_BOT_TOKEN تنظیم نشده — بات مدیریت تلگرام غیرفعال است")

    # ---------- ربات بله به‌عنوان سطح ادمین در حالت سلف‌بات (ترکیبی، اختیاری) ----------
    bale_bot_api = None
    if cfg.BALE_MODE == "user" and cfg.BALE_TOKEN:
        bale_bot_api = BotAPI(cfg.BALE_TOKEN, cfg.BALE_API_BASE)
        try:
            bale_bot_api.me = await bale_bot_api.get_me()
        except BotAPIError as e:
            log.error("ربات بله (ترکیبی) ناموفق — BALE_TOKEN را بررسی کنید: %s", e)
            bale_bot_api = None
        if bale_bot_api:
            log.info("حالت ترکیبی: ربات بله هم فعال — پنل ادمین در چت خصوصی ربات هم جواب می‌دهد")

    async def on_bale_bot_update(upd, offset):
        db.set_meta("bale_bot_offset", str(offset))
        m = upd.get("message")
        if not m:
            return
        chat = m.get("chat") or {}
        if chat.get("type") != "private":
            return  # کانال‌ها فقط از سشن کاربر می‌آیند (جلوگیری از دوباره‌کاری)
        uid = (m.get("from") or {}).get("id")
        text = m.get("text") or ""
        is_forward = bool(m.get("forward_from_chat") or m.get("forward_from"))
        if not (text.strip() or is_forward):
            return
        reply = await admin.handle("bale", chat.get("id"), uid, text, m)
        if reply:
            await bale_bot_api.send_message(chat.get("id"), reply)

    async def on_bale_update(upd, offset):
        db.set_meta("bale_offset", str(offset))
        dm = upd.get("deleted_messages")
        if dm is not None:
            # فقط سلف‌بات بله (aiobale) رویداد حذف می‌دهد → حذف بله→تلگرام
            await bridge.on_bale_delete(
                (dm.get("chat") or {}).get("id"), dm.get("message_ids") or [])
            return
        m = upd.get("message") or upd.get("channel_post")
        em = upd.get("edited_message") or upd.get("edited_channel_post")
        if em:
            await bridge.queue_bale_edit(em)
            return
        if not m:
            return
        chat = m.get("chat") or {}
        if chat.get("type") == "private":
            uid = (m.get("from") or {}).get("id")
            if cfg.BALE_MODE == "user":
                # سلف‌بات = حساب انسانی؛ هرگز به ناشناس‌ها پاسخ خودکار نده
                if not cfg.ADMIN_BALE_ID or int(uid or 0) != int(cfg.ADMIN_BALE_ID):
                    return
            text = m.get("text") or ""
            is_forward = bool(m.get("forward_from_chat") or m.get("forward_from"))
            if text.strip() or is_forward:
                reply = await admin.handle("bale", chat.get("id"), uid, text, m)
                if reply:
                    await bale.send_message(chat.get("id"), reply)
            return
        await bridge.queue_bale_msg(m)

    offset_raw = db.get_meta("bale_offset")
    offset = int(offset_raw) if offset_raw else None

    log.info("آماده دریافت پیام‌ها 🚀")
    tasks = [
        tg.run_until_disconnected(),
        bale.listen(on_bale_update, offset=offset, timeout=cfg.BALE_POLL_TIMEOUT),
        *bridge.workers(),
    ]
    if tg_bot_task:
        tasks.append(tg_bot_task)
    if bale_bot_api:
        bot_offset_raw = db.get_meta("bale_bot_offset")
        bot_offset = int(bot_offset_raw) if bot_offset_raw else None
        tasks.append(bale_bot_api.listen(
            on_bale_bot_update, offset=bot_offset, timeout=cfg.BALE_POLL_TIMEOUT))
    try:
        await asyncio.gather(*tasks)
    finally:
        if tg_bot_api:
            await tg_bot_api.close()
        if bale_bot_api:
            await bale_bot_api.close()
        await bale.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nخروج.")
