"""نقطهٔ مونتاژ داشبورد — Dashboard: موتورها را می‌سازد و aiohttp را بالا می‌آورد.

سازگاری کامل با کد قدیمی: Dashboard.ensure_credentials / change_password /
change_user (که admin.py و wizard.py صدا می‌زنند) به AuthEngine delegate می‌شوند.
"""
from __future__ import annotations

import logging

from aiohttp import web

from .api import COOKIE, error_mw, routes, security_mw
from .auth import AuthEngine
from .context import RuntimeCtx
from .engines import ControlEngine, LogsEngine, OpsEngine, PairsEngine, StatusEngine

log = logging.getLogger("dashboard")


class Dashboard:
    """فاساد داشبورد: مالک موتورها و سرور وب."""

    def __init__(self, db, store, cfg, rt: dict | None = None) -> None:
        self.ctx = RuntimeCtx(db, store, cfg, rt)
        self.auth = AuthEngine(store)
        self.status = StatusEngine(self.ctx)
        self.pairs = PairsEngine(self.ctx)
        self.control = ControlEngine(self.ctx)
        self.logs = LogsEngine(self.ctx)
        self.ops = OpsEngine(self.ctx)
        middlewares = [error_mw, security_mw]
        self.app = web.Application(middlewares=middlewares)
        self.app["dash"] = self
        self.app.add_routes(routes())
        self._runner: web.AppRunner | None = None

    # ───────────────── سازگاری با کد بات (admin.py / wizard.py) ─────────────────
    @property
    def db(self):
        return self.ctx.db

    @property
    def store(self):
        return self.ctx.store

    @classmethod
    def ensure_credentials(cls, store) -> tuple[str, str | None, bool]:
        return AuthEngine(store).ensure_credentials()

    @classmethod
    def set_credentials(cls, store, user: str, password: str) -> None:
        AuthEngine(store).set_credentials(user, password)

    @classmethod
    def change_password(cls, store, new: str) -> None:
        AuthEngine(store).change_password(new)

    @classmethod
    def change_user(cls, store, user: str) -> None:
        AuthEngine(store).change_user(user)

    # ───────────────────────────── چرخهٔ کار ─────────────────────────────
    async def start(self) -> None:
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, getattr(self.ctx.cfg, "DASH_HOST", "0.0.0.0"),
                           int(getattr(self.ctx.cfg, "DASH_PORT", 8080)))
        await site.start()
        log.info("🌐 داشبورد: http://%s:%s (یوزرنیم/رمز: با /dashboard در بات بگیرید)",
                 getattr(self.ctx.cfg, "DASH_HOST", "0.0.0.0"),
                 getattr(self.ctx.cfg, "DASH_PORT", 8080))

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    # برای تست‌های HTTP که به کوکی/سشن دسترسی دارند
    @property
    def session_cookie(self) -> str:
        return COOKIE
