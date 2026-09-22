"""نقطه شروع پل همگام‌سازی تلگرام ⇄ بله."""
from __future__ import annotations

import asyncio
import logging
import sys

from telethon import TelegramClient

import config as cfg
from bridge.admin import Admin
from bridge.bale_api import BaleAPI, BaleError
from bridge.db import DB
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
    problems = cfg.validate()
    if problems:
        for p in problems:
            log.error("پیکربندی: %s", p)
        sys.exit(1)

    db = DB(cfg.DB_PATH)
    bale = BaleAPI(cfg.BALE_TOKEN, cfg.BALE_API_BASE)

    try:
        bale_me = await bale.get_me()
    except BaleError as e:
        log.error("اتصال به بله ناموفق — توکن ربات را بررسی کنید: %s", e)
        sys.exit(1)
    log.info("ربات بله: @%s (id=%s)", bale_me.get("username"), bale_me.get("id"))

    tg = TelegramClient(str(cfg.SESSION_PATH), cfg.TG_API_ID, cfg.TG_API_HASH)
    await tg.start(phone=cfg.TG_PHONE or None)
    me = await tg.get_me()
    log.info("حساب تلگرام: %s (id=%s)", me.username or me.first_name, me.id)

    bridge = Bridge(tg, bale, db, cfg, me.id, bale_me)
    admin = Admin(db, bale, tg, bridge, cfg)
    register_tg(tg, bridge, admin, me.id)

    if not cfg.ADMIN_BALE_ID:
        log.warning("ADMIN_BALE_ID تنظیم نشده — برای فعال‌سازی دستورات، در ربات بله /start بزنید")

    pairs = db.list_pairs()
    log.info("%d جفت کانال فعال است", len(pairs))

    async def on_bale_update(upd, offset):
        db.set_meta("bale_offset", str(offset))
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
            text = m.get("text") or ""
            if text.strip() or m.get("forward_from_chat") or m.get("forward_from"):
                reply = await admin.handle("bale", chat.get("id"), uid, text, m)
                if reply:
                    await bale.send_message(chat.get("id"), reply)
            return
        await bridge.queue_bale_msg(m)

    offset_raw = db.get_meta("bale_offset")
    offset = int(offset_raw) if offset_raw else None

    log.info("آماده دریافت پیام‌ها 🚀")
    await asyncio.gather(
        tg.run_until_disconnected(),
        bale.listen(on_bale_update, offset=offset, timeout=cfg.BALE_POLL_TIMEOUT),
        *bridge.workers(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nخروج.")
