"""نقطه شروع پل همگام‌سازی تلگرام ⇄ بله.

دو حالت بوت:
• حالت نصاب — فقط TG_BOT_TOKEN لازم است؛ بات تلگرام ویزارد نصب را می‌چرخاند
  (سلف تلگرام، سلف بله، ربات بله، جفت کانال‌ها، تست دسترسی) و در پایان خودش ری‌استارت می‌شود.
• حالت کامل — همه حساب‌ها از store/.env آماده‌اند؛ پل کامل بالا می‌آید.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

import config as cfg
from bridge import logbuf
from bridge.admin import Admin
from bridge.bale import BaleEventRouter
from bridge.bot_api import BotAPI, BotAPIError
from bridge.dashboard import Dashboard
from bridge.db import DB
from bridge.store import Store
from bridge.tgbot import TgAdminBot
from bridge.tguser import TgSelfSession
from bridge.tguser import register as register_tg
from bridge.transfer import Bridge
from bridge.wizard import Wizard

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


def _apply_store_overrides(cfg, store: Store) -> None:
    """پیکربندی ذخیره‌شده در ویزارد (.env حداقلی) را روی cfg اعمال می‌کند."""
    admin = store.admin_tg_id()
    if admin and not cfg.ADMIN_TG_ID:
        cfg.ADMIN_TG_ID = admin
    api = store.tg_api()
    if api:
        if not cfg.TG_API_ID:
            cfg.TG_API_ID = int(api.get("api_id") or 0)
        if not cfg.TG_API_HASH:
            cfg.TG_API_HASH = api.get("api_hash", "")
    bb = store.bale_bot()
    if bb and not cfg.BALE_TOKEN:
        cfg.BALE_TOKEN = bb.get("token", "")


async def _run_installer(db: DB, store: Store):
    """فقط بات کنترل + ویزارد نصب."""
    if not cfg.TG_BOT_TOKEN:
        log.error("TG_BOT_TOKEN در .env لازم است — فقط همین یکی!")
        sys.exit(1)
    log.warning("نصب ناقص است — حالت نصاب: در بات تلگرام /start بزنید و ویزارد را کامل کنید")
    log_handler = logbuf.install()
    started_at = time.time()
    api = BotAPI(cfg.TG_BOT_TOKEN, cfg.TG_BOT_API_BASE)
    try:
        api.me = await api.get_me()
    except BotAPIError as e:
        log.error("بات مدیریت تلگرام ناموفق — TG_BOT_TOKEN را بررسی کنید: %s", e)
        sys.exit(1)
    wizard = Wizard(api, db, cfg, store)
    bot = TgAdminBot(api, None, db, cfg, wizard=wizard, store=store)
    dash = Dashboard(db, store, cfg, {"log_buffer": log_handler, "started_at": started_at})
    if cfg.DASH_ENABLED:
        await dash.start()
    try:
        await bot.start()
    finally:
        if cfg.DASH_ENABLED:
            await dash.stop()
        await api.close()


async def main():
    print(BANNER)
    started_at = time.time()
    log_handler = logbuf.install()

    db = DB(cfg.DB_PATH)
    store = Store(db)
    _apply_store_overrides(cfg, store)

    if not store.installed(cfg):
        await _run_installer(db, store)
        return

    problems = cfg.validate()
    if problems:
        for p in problems:
            log.error("پیکربندی: %s", p)
        sys.exit(1)

    # ---------- سمت بله: سلف (aiobale) یا ربات (BotAPI) ----------
    if cfg.BALE_MODE == "user" or store.bale_self():
        from bridge.bale import BaleUserAPI

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

    # ---------- سمت تلگرام: سلف (Telethon) ----------
    tg = TgSelfSession.build(cfg.SESSION_PATH, cfg.TG_API_ID, cfg.TG_API_HASH)
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

    dash = Dashboard(db, store, cfg, {
        "admin": admin, "bridge": bridge, "tg": tg, "bale": bale,
        "tg_me": {"id": me.id, "username": me.username, "first_name": me.first_name},
        "bale_me": bale_me,
        "log_buffer": log_handler, "started_at": started_at,
    })
    if cfg.DASH_ENABLED:
        await dash.start()

    if not cfg.ADMIN_TG_ID:
        log.warning("ادمین تلگرام تعیین نشده — اولین /start در بات مدیریت ادمین می‌شود")

    pairs = db.list_pairs()
    log.info("%d جفت کانال فعال است", len(pairs))

    # ---------- بات مدیریت تلگرام + ویزارد ----------
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
            wizard = Wizard(tg_bot_api, db, cfg, store, admin=admin)
            tgbot = TgAdminBot(tg_bot_api, admin, db, cfg, wizard=wizard, store=store)
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

    router = BaleEventRouter(db, cfg, bridge=bridge, admin=admin, bale=bale)

    offset_raw = db.get_meta("bale_offset")
    offset = int(offset_raw) if offset_raw else None

    log.info("آماده دریافت پیام‌ها 🚀")
    tasks = [
        tg.run_until_disconnected(),
        bale.listen(router.handle_update, offset=offset, timeout=cfg.BALE_POLL_TIMEOUT),
        *bridge.workers(),
    ]
    if tg_bot_task:
        tasks.append(tg_bot_task)
    if bale_bot_api:
        bot_offset_raw = db.get_meta("bale_bot_offset")
        bot_offset = int(bot_offset_raw) if bot_offset_raw else None
        tasks.append(bale_bot_api.listen(
            router.panel_handler(bale_bot_api), offset=bot_offset,
            timeout=cfg.BALE_POLL_TIMEOUT))
    try:
        await asyncio.gather(*tasks)
    finally:
        if cfg.DASH_ENABLED:
            await dash.stop()
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
