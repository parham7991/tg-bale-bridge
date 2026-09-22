"""DashCommandsEngine — داشبورد وب از داخل پنل ادمین: dashboard / passwd / dashuser."""
from __future__ import annotations

import logging

logger = logging.getLogger("bridge.admin.dash")


class DashCommandsEngine:
    """نشانی و اعتبارنامهٔ داشبورد — از موتور داشبورد (classmethods)."""

    def __init__(self, adm) -> None:
        self.adm = adm                  # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند

    @property
    def db(self):
        return self.adm.db

    @property
    def cfg(self):
        return self.adm.cfg

    async def dashboard(self, platform, args, msg):
        """نشانی + اعتبارنامهٔ داشبورد وب (رمز اولیه فقط یک بار نشان داده می‌شود)."""
        from ..dashboard import Dashboard
        from ..store import Store

        if not getattr(self.cfg, "DASH_ENABLED", True):
            return "داشبورد خاموش است — DASH_ENABLED=1 بگذارید و ری‌استارت کنید."
        st = Store(self.db)
        user, password, created = Dashboard.ensure_credentials(st)
        host = getattr(self.cfg, "DASH_HOST", "0.0.0.0")
        port = getattr(self.cfg, "DASH_PORT", 8080)
        addr = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://<IP-سرور>:{port}"
        lines = [f"🌐 داشبورد وب: {addr}", f"▫️ یوزرنیم: {user}"]
        if created:
            lines.append(f"▫️ رمز اولیه: {password}")
            lines.append("⚠️ این رمز فقط همین‌جا نشان داده می‌شود — با /passwd عوضش کنید.")
        else:
            lines.append("▫️ رمز: قبلاً ست شده — با /passwd <رمز_جدید> عوض کنید.")
        return "\n".join(lines)

    async def passwd(self, platform, args, msg):
        from ..dashboard import Dashboard
        from ..store import Store

        new = (args or [""])[0]
        if len(new) < 6:
            return "فرمت: /passwd <رمز_جدید> — حداقل ۶ کاراکتر"
        Dashboard.change_password(Store(self.db), new)
        return "✅ رمز داشبورد تغییر کرد."

    async def dashuser(self, platform, args, msg):
        from ..dashboard import Dashboard
        from ..store import Store

        user = (args or [""])[0]
        if not user or " " in user:
            return "فرمت: /dashuser <یوزرنیم>"
        Dashboard.change_user(Store(self.db), user)
        return f"✅ یوزرنیم داشبورد: {user}"
