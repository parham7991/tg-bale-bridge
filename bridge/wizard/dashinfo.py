"""DashInfoEngine — نمایش آدرس و اعتبارنامهٔ اولیهٔ داشبورد وب داخل ویزارد."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bridge.wizard.dashinfo")


class DashInfoEngine:
    """اطلاعات داشبورد — اعتبارنامه از موتور داشبورد می‌آید."""

    def __init__(self, wiz: Any, cfg: Any, store: Any) -> None:
        self.wiz = wiz
        self.cfg = cfg
        self.store = store

    async def info(self, chat_id) -> None:
        from ..dashboard import Dashboard

        if not getattr(self.cfg, "DASH_ENABLED", True):
            await self.wiz._send(chat_id, "داشبورد خاموش است (DASH_ENABLED=0).")
            return
        user, password, created = Dashboard.ensure_credentials(self.store)
        host = getattr(self.cfg, "DASH_HOST", "0.0.0.0")
        port = getattr(self.cfg, "DASH_PORT", 8080)
        addr = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://<IP-سرور>:{port}"
        text = f"🌐 داشبورد وب:\n{addr}\n▫️ یوزرنیم: {user}\n"
        text += (f"▫️ رمز اولیه: {password}\n⚠️ فقط همین‌جا نشان داده می‌شود — عوضش کنید!\n"
                 if created else
                 "▫️ رمز: ست شده است (با /passwd عوض کنید یا از خود داشبورد).\n")
        await self.wiz._send(chat_id, text, self.wiz._menu_kb())
