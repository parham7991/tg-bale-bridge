"""SystemCommandsEngine — دستورات اطلاعاتی: status / whoami / logs."""
from __future__ import annotations

import logging
import time

from .types_map import fmt_duration

logger = logging.getLogger("bridge.admin.system")


class SystemCommandsEngine:
    """وضعیت پل، هویت حساب‌ها و دمِ لاگ."""

    def __init__(self, adm, surfaces) -> None:
        self.adm = adm                  # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند
        self.surfaces = surfaces        # SurfacesEngine

    @property
    def db(self):
        return self.adm.db

    @property
    def tg(self):
        return self.adm.tg

    @property
    def bridge(self):
        return self.adm.bridge

    @property
    def bale_bot(self):
        return self.adm.bale_bot or {}

    @property
    def tg_bot_info(self):
        return self.adm.tg_bot_info or {}

    @property
    def started_at(self):
        return self.adm.started_at

    @property
    def log_buffer(self):
        return self.adm.log_buffer

    async def status(self, platform, args, msg):
        stats = self.db.stats()
        me = self.bale_bot.get("username") or self.bale_bot.get("id") or "?"
        try:
            tg_me = await self.tg.get_me()
            tg_name = f"@{tg_me.username}" if tg_me.username else tg_me.first_name
        except Exception:
            tg_name = "?"
        bot_name = self.tg_bot_info.get("username") or "غیرفعال"
        state = ("⏸ متوقف (همگام‌سازی خاموش)" if self.bridge.paused
                 else "▶️ در حال همگام‌سازی")
        uptime = fmt_duration(time.time() - self.started_at)
        bale_desc = (f"حساب بله (سلف‌بات): {me}" if self.surfaces.is_user_mode()
                     else f"ربات بله: {me}")
        coverage = ("حذف دوطرفه 🗑" if self.surfaces.is_user_mode()
                    else "حذف (تلگرام→بله)")
        lines = [
            "🩺 وضعیت پل",
            f"▫️ حالت: {state}",
            f"▫️ حساب تلگرام (سلف): {tg_name}",
            f"▫️ {bale_desc}",
            f"▫️ بات مدیریت تلگرام: {bot_name}",
            f"▫️ پنل‌های مدیریت: {self.surfaces.surfaces(self.tg_bot_info)}",
            f"▫️ جفت‌های کانال: {stats['pairs']}",
            f"▫️ پیام‌های همگام‌شده (نگاشت‌شده): {stats['mapped']}",
            f"▫️ زمان فعالیت: {uptime}",
            f"▫️ پوشش: متن/رسانه/آلبوم/فوروارد/ریپلای/ویرایش + {coverage}",
        ]
        return "\n".join(lines)

    async def whoami(self, platform, args, msg, current_user_id=None):
        try:
            tg_me = await self.tg.get_me()
            tg_name = f"@{tg_me.username}" if tg_me.username else tg_me.first_name
            tg_line = f"{tg_name} (id={tg_me.id})"
        except Exception:
            tg_line = "؟"
        bale_user = self.bale_bot.get("username")
        bale_name = f"@{bale_user}" if bale_user else (self.bale_bot.get("first_name") or "?")
        mode_lbl = self.surfaces.bale_mode_label()
        bale_line = f"{bale_name} (id={self.bale_bot.get('id')}) — {mode_lbl}"
        bot_line = (f"@{self.tg_bot_info.get('username')} (id={self.tg_bot_info.get('id')})"
                    if self.tg_bot_info else "غیرفعال")
        return ("👤 هویت\n"
                f"▫️ شما (ادمین): {current_user_id}\n"
                f"▫️ سلف‌بات / حساب تلگرام: {tg_line}\n"
                f"▫️ بله: {bale_line}\n"
                f"▫️ بات مدیریت تلگرام: {bot_line}\n"
                f"▫️ پنل‌های فعال: {self.surfaces.surfaces(self.tg_bot_info)}")

    def logs(self, platform, args, msg):
        if not self.log_buffer:
            return "لاگ در دسترس نیست."
        n = 15
        if args and args[0].isdigit():
            n = int(args[0])
        lines = self.log_buffer.tail(n)
        if not lines:
            return "هنوز لاگی ثبت نشده."
        return "📜 آخرین لاگ‌ها:\n" + "\n".join(lines)
