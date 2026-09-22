"""Runtime — نمای ترکیب چرخهٔ اجرا (ریشهٔ ترکیب بستهٔ runtime).

جریان دقیقاً مثل main قدیمی:
    ۱) overrides → اعمال store روی cfg
    ۲) نصب ناقص؟ → InstallerEngine (بات کنترل + ویزارد)
    ۳) validate → سمت بله → سمت تلگرام → پل+ادمین → ثبت رویدادها
    ۴) داشبورد + بات‌های کنترلی → صف وظایف → gather → پاک‌سازی

موتورها:
    overrides  → OverridesEngine   · installer → InstallerEngine
    wiring     → WiringEngine      · bots      → ControlBotsEngine
    lifecycle  → LifecycleEngine   · types_map → بانر + حالت نصاب
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

import config as cfg

from ..bale import BaleEventRouter
from ..db import DB
from ..logbuf import install as install_logbuf
from ..store import Store
from ..tguser import register as register_tg
from .bots import ControlBotsEngine
from .installer import InstallerEngine
from .lifecycle import LifecycleEngine
from .overrides import OverridesEngine
from .types_map import BANNER, is_installer_mode
from .wiring import WiringEngine

log = logging.getLogger("main")


class Runtime:
    """چرخهٔ کامل اجرای پل — دو حالت بوت: نصاب و کامل."""

    def __init__(self, cfg=cfg) -> None:
        self.cfg = cfg

    # ───────────────────────────── جریان اصلی ─────────────────────────────
    async def main(self) -> None:
        print(BANNER)
        started_at = time.time()
        log_handler = install_logbuf()

        db = DB(self.cfg.DB_PATH)
        store = Store(db)
        OverridesEngine(store).apply(self.cfg)

        if is_installer_mode(self.cfg, store):
            await InstallerEngine(self.cfg, db, store).run()
            return

        problems = self.cfg.validate()
        if problems:
            for p in problems:
                log.error("پیکربندی: %s", p)
            sys.exit(1)

        wiring = WiringEngine(self.cfg, db, store)
        bale, bale_me = await wiring.bale_side()
        tg, me = await wiring.tg_side()

        bridge, admin = wiring.bridge_and_admin(
            tg, me, bale, bale_me, log_handler, started_at)
        register_tg(tg, bridge, admin, me.id)

        dash = wiring.dashboard(admin, bridge, tg, bale, me, bale_me,
                                log_handler, started_at)
        if self.cfg.DASH_ENABLED:
            await dash.start()

        if not self.cfg.ADMIN_TG_ID:
            log.warning("ادمین تلگرام تعیین نشده — اولین /start در بات مدیریت ادمین می‌شود")

        pairs = db.list_pairs()
        log.info("%d جفت کانال فعال است", len(pairs))

        tg_bot_api, tg_bot_task, bale_bot_api = await ControlBotsEngine(
            self.cfg, db, store).start(admin=admin)

        router = BaleEventRouter(db, self.cfg, bridge=bridge, admin=admin, bale=bale)
        lifecycle = LifecycleEngine(self.cfg, db)
        tasks = lifecycle.build_tasks(tg, bale, bridge, router,
                                      tg_bot_task=tg_bot_task,
                                      bale_bot_api=bale_bot_api)
        await lifecycle.run_all(tasks, dash=dash, tg_bot_api=tg_bot_api,
                                bale_bot_api=bale_bot_api, bale=bale)

    # ───────────────────────────── نقطهٔ ورود CLI ─────────────────────────────
    @classmethod
    def cli(cls) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        )
        logging.getLogger("telethon").setLevel(logging.WARNING)
        try:
            asyncio.run(cls().main())
        except KeyboardInterrupt:
            print("\nخروج.")
