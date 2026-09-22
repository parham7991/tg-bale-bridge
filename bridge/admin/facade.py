"""Admin — نمای سازگاری پنل ادمین (ریشهٔ ترکیب بستهٔ admin).

سطح عمومی دقیقاً مثل قبل: ``Admin(db, bale, tg, bridge, cfg, log_buffer=None,
started_at=None, tg_bot_info=None)`` با ``handle(platform, chat_id, user_id,
text, msg)`` و همهٔ متدهای ``cmd_*``/``_parse``/``_resolve_*`` — اما داخل،
هر بخش به موتور خودش تفویض می‌شود:

    types_map     → ثابت‌ها + پارس        · surfaces    → SurfacesEngine
    resolver      → ResolverEngine        · pairs_cmds  → PairsCommandsEngine
    system_cmds   → SystemCommandsEngine  · control_cmds → ControlCommandsEngine
    ops_cmds      → OpsCommandsEngine     · dash_cmds   → DashCommandsEngine
    probes        → توابع سازگاری پروب

نکتهٔ تست‌ها: همهٔ موتورها از طریق نما (self.*) به وابستگی‌ها می‌رسند، پس
پچ‌کردن اتریبیوت‌های نما (مثل self.bale/self.tg) روی رفتار موتورها هم اثر می‌گذارد.
"""
from __future__ import annotations

import logging
import time

from .control_cmds import ControlCommandsEngine
from .dash_cmds import DashCommandsEngine
from .ops_cmds import OpsCommandsEngine
from .pairs_cmds import PairsCommandsEngine
from .resolver import ResolverEngine
from .surfaces import SurfacesEngine
from .system_cmds import SystemCommandsEngine
from .types_map import HELP, MINIMAL_HELP, parse_command

log = logging.getLogger("admin")

SETUP_HINT = ("🧙‍♂️ ویزارد نصب فقط در **بات مدیریت تلگرام** باز می‌شود: /setup\n"
              "(همه‌چیز بدون هیچ شناسه عددی همان‌جا ست می‌شود)")
ID_HINT = ("روی یک پیام فوروارد‌شده ریپلای کنید یا آن را فوروارد کنید "
           "تا شناسه چت مبدأ را بگویم.")


class Admin:
    """دستورات مدیریتی — ربات بله، بات مدیریت تلگرام یا «پیام‌های ذخیره‌شده»."""

    def __init__(self, db, bale, tg, bridge, cfg,
                 log_buffer=None, started_at=None, tg_bot_info=None):
        self.db = db
        self.bale = bale
        self.tg = tg
        self.bridge = bridge
        self.cfg = cfg
        self.bale_bot = bridge.bale_bot
        self.log_buffer = log_buffer
        self.started_at = started_at or time.time()
        self.tg_bot_info = tg_bot_info or {}
        self._current_user_id = None
        # ── موتورها (به خود نما وصل‌اند — اتریبیوت‌ها زنده خوانده می‌شوند) ──
        self.surfaces_engine = SurfacesEngine(cfg)
        self.resolver = ResolverEngine(self)
        self.pairs_cmd = PairsCommandsEngine(self, self.resolver)
        self.system_cmd = SystemCommandsEngine(self, self.surfaces_engine)
        self.control_cmd = ControlCommandsEngine(self)
        self.ops_cmd = OpsCommandsEngine(self)
        self.dash_cmd = DashCommandsEngine(self)

    # ---------------------------------------------------------- سطوح مدیریتی
    def _is_user_mode(self) -> bool:
        return self.surfaces_engine.is_user_mode()

    def _bale_mode_label(self) -> str:
        return self.surfaces_engine.bale_mode_label()

    def _surfaces(self) -> str:
        return self.surfaces_engine.surfaces(self.tg_bot_info)

    # ---------------------------------------------------------- ورودی
    async def handle(self, platform: str, chat_id, user_id, text: str,
                     msg=None) -> str | None:
        text = (text or "").strip()

        if platform == "bale":
            if not self.cfg.ADMIN_BALE_ID:
                return (f"🔐 آیدی عددی شما در بله: {user_id}\n\n"
                        "این مقدار را در فایل .env در کلید ADMIN_BALE_ID "
                        "بگذارید و برنامه را ری‌استارت کنید تا دستورات مدیریتی باز شود.")
            if int(user_id) != int(self.cfg.ADMIN_BALE_ID):
                return None

        if platform == "tgbot":
            if not getattr(self.cfg, "ADMIN_TG_ID", 0):
                return (f"🔐 آیدی عددی شما در تلگرام: {user_id}\n\n"
                        "این مقدار را در فایل .env در کلید ADMIN_TG_ID بگذارید "
                        "و برنامه را ری‌استارت کنید تا دستورات مدیریتی باز شود.")
            if int(user_id) != int(self.cfg.ADMIN_TG_ID):
                return None

        self._current_user_id = user_id
        cmd, args = self._parse(text)
        if cmd is None:
            if text.startswith("/"):
                return "دستور ناشناخته — /help را ببینید."
            info = await self._describe_forward(platform, msg)
            return info or MINIMAL_HELP
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            return "دستور ناشناخته — /help را ببینید."
        try:
            return await handler(platform, args, msg)
        except Exception as e:
            log.exception("command failed")
            return f"⚠️ خطا: {e}"

    def _parse(self, text: str):
        """از نگاشت‌های خالص — پارس دستور."""
        return parse_command(text)

    # ---------------------------------------------------------- دستورات پایه
    async def cmd_help(self, platform, args, msg):
        return HELP

    async def cmd_setup(self, platform, args, msg):
        return SETUP_HINT

    async def cmd_id(self, platform, args, msg):
        info = await self._describe_forward(platform, msg)
        return info or ID_HINT

    # ---------------------------------------------------------- تفویض: اطلاعات
    async def cmd_status(self, platform, args, msg):
        return await self.system_cmd.status(platform, args, msg)

    async def cmd_whoami(self, platform, args, msg):
        return await self.system_cmd.whoami(platform, args, msg,
                                            current_user_id=self._current_user_id)

    async def cmd_logs(self, platform, args, msg):
        return self.system_cmd.logs(platform, args, msg)

    # ---------------------------------------------------------- تفویض: جفت‌ها
    async def cmd_add(self, platform, args, msg):
        return await self.pairs_cmd.add(platform, args, msg)

    async def cmd_remove(self, platform, args, msg):
        return self.pairs_cmd.remove(platform, args, msg)

    async def cmd_mode(self, platform, args, msg):
        return self.pairs_cmd.mode(platform, args, msg)

    async def cmd_list(self, platform, args, msg):
        return self.pairs_cmd.list(platform, args, msg)

    # ---------------------------------------------------------- تفویض: کنترل
    async def cmd_pause(self, platform, args, msg):
        return await self.control_cmd.pause(platform, args, msg)

    async def cmd_resume(self, platform, args, msg):
        return await self.control_cmd.resume(platform, args, msg)

    async def cmd_test(self, platform, args, msg):
        return await self.control_cmd.test(platform, args, msg)

    # ---------------------------------------------------------- تفویض: عملیات
    async def cmd_access(self, platform, args, msg):
        return await self.ops_cmd.access(platform, args, msg)

    async def cmd_promote(self, platform, args, msg):
        return await self.ops_cmd.promote(platform, args, msg)

    # ---------------------------------------------------------- تفویض: داشبورد
    async def cmd_dashboard(self, platform, args, msg):
        return await self.dash_cmd.dashboard(platform, args, msg)

    async def cmd_passwd(self, platform, args, msg):
        return await self.dash_cmd.passwd(platform, args, msg)

    async def cmd_dashuser(self, platform, args, msg):
        return await self.dash_cmd.dashuser(platform, args, msg)

    # ---------------------------------------------------------- شناسه‌ها
    async def _describe_forward(self, platform, msg) -> str | None:
        return await self.resolver.describe_forward(platform, msg)

    async def _resolve_tg(self, ref: str):
        return await self.resolver.resolve_tg(ref)

    async def _resolve_bale(self, ref: str):
        """از موتور gateway بله — همان منطق، یک‌جا نگهداری می‌شود."""
        from ..bale import BaleBotGateway

        return await BaleBotGateway(self.bale).resolve(ref)


# سازگاری — قالب‌بندی مدت فعالیت در سطح ماژول هم در دسترس است
from .types_map import _fmt_duration, fmt_duration  # noqa: E402,F401
