"""دستورات مدیریتی — ربات بله، بات مدیریت تلگرام یا «پیام‌های ذخیره‌شده»."""
from __future__ import annotations

import logging
import re
import time

from telethon import utils as tg_utils

log = logging.getLogger("admin")

MODE_ALIASES = {
    "both": "both", "دوطرفه": "both", "دودطرفه": "both", "دو طرفه": "both",
    "tg2bale": "tg2bale", "t2b": "tg2bale", "tg2b": "tg2bale",
    "تلگرام_به_بله": "tg2bale", "تلگرامبهبله": "tg2bale",
    "bale2tg": "bale2tg", "b2t": "bale2tg", "b2tg": "bale2tg",
    "بله_به_تلگرام": "bale2tg", "بلهبهتلگرام": "bale2tg",
}
MODE_LABELS = {"both": "دوطرفه ↔", "tg2bale": "تلگرام→بله", "bale2tg": "بله→تلگرام"}

CMD_ALIASES = {
    "start": "help", "help": "help", "راهنما": "help", "کمک": "help",
    "add": "add", "افزودن": "add", "اضافه": "add", "جفت": "add",
    "remove": "remove", "del": "remove", "delete": "remove",
    "حذف": "remove", "پاک": "remove",
    "list": "list", "ls": "list", "لیست": "list",
    "mode": "mode", "حالت": "mode",
    "test": "test", "تست": "test",
    "status": "status", "وضعیت": "status",
    "id": "id", "شناسه": "id",
    "whoami": "whoami", "هویت": "whoami", "من": "whoami",
    "pause": "pause", "توقف": "pause", "مکث": "pause", "قفل": "pause",
    "resume": "resume", "ادامه": "resume", "ازسرگیری": "resume",
    "logs": "logs", "لاگ": "logs", "لاگ‌ها": "logs",
    "access": "access", "دسترسی": "access",
    "promote": "promote", "ارتقا": "promote", "ادمین_کردن": "promote",
    "dashboard": "dashboard", "داشبورد": "dashboard",
    "passwd": "passwd", "رمز": "passwd", "پسورد": "passwd",
    "dashuser": "dashuser",
    "setup": "setup", "نصب": "setup",
}

HELP = """🤖 پل همگام‌سازی تلگرام ⇄ بله

هر پیامی (متن، عکس، ویدیو، وویس، فایل، استیکر، آلبوم، فورواردی، جواب/ریپلای) را بین کانال‌های
تلگرام و بله جابه‌جا می‌کنم؛ ویرایش و حذف پیام در تلگرام هم در بله اعمال می‌شود.

▫️ /add <کانال_تلگرام> <کانال_بله> [حالت]
   نمونه: /add @my_tg_channel @my_bale_channel both
   نمونه: /add -1001234567890 987654321 tg2bale
   حالت‌ها: both (دوطرفه) | tg2bale | bale2tg

▫️ /list — نمایش جفت‌های متصل
▫️ /mode <شناسه> <حالت> — تغییر جهت همگام‌سازی
▫️ /remove <شناسه> — حذف یک جفت
▫️ /test <شناسه> — ارسال پیام آزمایشی
▫️ /id — در پاسخ/فوروارد پیام، شناسه چت را می‌گوید (برای /add)
▫️ /status — وضعیت ربات و سلف‌بات
▫️ /whoami — هویت حساب‌ها (سلف، بله، بات مدیریت)
▫️ /pause · /resume — توقف/ادامهٔ موقت همگام‌سازی
▫️ /logs [تعداد] — آخرین خطوط لاگ (پیش‌فرض ۱۵)
▫️ /access — تست واقعی دسترسی سلف‌ها/ربات به کانال‌های هر جفت
▫️ /promote [@ربات_بله] — سلف بله، ربات را به کانال‌ها اضافه و ادمین می‌کند
▫️ /dashboard — نشانی + یوزرنیم/رمز داشبورد وب
▫️ /passwd <رمز_جدید> · /dashuser <یوزرنیم> — تغییر اعتبارنامهٔ داشبورد
▫️ /setup — باز کردن ویزارد نصب (فقط در بات مدیریت تلگرام)
▫️ /id — در پاسخ/فوروارد پیام، شناسه چت را می‌گوید (برای /add)

💡 برای فهمیدن شناسه عددی کانال‌ها کافی است یک پیام از آن‌ها را اینجا فوروارد کنید."""

MINIMAL_HELP = """🤖 پل تلگرام ⇄ بله آماده است.
یک پیام از کانال تلگرام یا بله را فوروارد کنید تا شناسه‌اش را بگویم، بعد:
/add <کانال_تلگرام> <کانال_بله> [both|tg2bale|bale2tg]

دستورات: /help · /list · /status · /whoami · /pause · /resume · /logs"""


class Admin:
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

    # ---------------------------------------------------------- سطوح مدیریتی
    def _is_user_mode(self) -> bool:
        return getattr(self.cfg, "BALE_MODE", "bot") == "user"

    def _bale_mode_label(self) -> str:
        return "سلف‌بات بله (BALE_MODE=user)" if self._is_user_mode() else "ربات بله"

    def _surfaces(self) -> str:
        """پنل‌های فعال مدیریتی — همه به یک پنل وصل‌اند."""
        names = []
        if self._is_user_mode():
            names.append("خودچت بله (پیام به خودتان)")
            if getattr(self.cfg, "BALE_TOKEN", ""):
                names.append("ربات بله")
        else:
            names.append("ربات بله")
        if self.tg_bot_info:
            names.append("بات تلگرام")
        names.append("Saved Messages تلگرام")
        return " + ".join(names)

    # ---------------------------------------------------------- ورودی
    async def handle(self, platform: str, chat_id, user_id, text: str, msg=None) -> str | None:
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
        if not text:
            return None, []
        if text.startswith("/"):
            parts = text.split()
            raw = parts[0][1:].split("@")[0].lower()
            cmd = CMD_ALIASES.get(raw)
            return cmd, parts[1:]
        parts = text.split()
        cmd = CMD_ALIASES.get(parts[0].lower())
        if cmd:
            return cmd, parts[1:]
        return None, []

    # ---------------------------------------------------------- دستورات
    async def cmd_help(self, platform, args, msg):
        return HELP

    async def cmd_status(self, platform, args, msg):
        stats = self.db.stats()
        me = self.bale_bot.get("username") or self.bale_bot.get("id") or "?"
        try:
            tg_me = await self.tg.get_me()
            tg_name = f"@{tg_me.username}" if tg_me.username else tg_me.first_name
        except Exception:
            tg_name = "?"
        bot_name = self.tg_bot_info.get("username") or "غیرفعال"
        state = "⏸ متوقف (همگام‌سازی خاموش)" if self.bridge.paused else "▶️ در حال همگام‌سازی"
        uptime = _fmt_duration(time.time() - self.started_at)
        bale_desc = f"حساب بله (سلف‌بات): {me}" if self._is_user_mode() else f"ربات بله: {me}"
        coverage = "حذف دوطرفه 🗑" if self._is_user_mode() else "حذف (تلگرام→بله)"
        lines = [
            "🩺 وضعیت پل",
            f"▫️ حالت: {state}",
            f"▫️ حساب تلگرام (سلف): {tg_name}",
            f"▫️ {bale_desc}",
            f"▫️ بات مدیریت تلگرام: {bot_name}",
            f"▫️ پنل‌های مدیریت: {self._surfaces()}",
            f"▫️ جفت‌های کانال: {stats['pairs']}",
            f"▫️ پیام‌های همگام‌شده (نگاشت‌شده): {stats['mapped']}",
            f"▫️ زمان فعالیت: {uptime}",
            f"▫️ پوشش: متن/رسانه/آلبوم/فوروارد/ریپلای/ویرایش + {coverage}",
        ]
        return "\n".join(lines)

    async def cmd_whoami(self, platform, args, msg):
        try:
            tg_me = await self.tg.get_me()
            tg_name = f"@{tg_me.username}" if tg_me.username else tg_me.first_name
            tg_line = f"{tg_name} (id={tg_me.id})"
        except Exception:
            tg_line = "؟"
        bale_user = self.bale_bot.get("username")
        bale_name = f"@{bale_user}" if bale_user else (self.bale_bot.get("first_name") or "?")
        bale_line = f"{bale_name} (id={self.bale_bot.get('id')}) — {self._bale_mode_label()}"
        bot_line = (f"@{self.tg_bot_info.get('username')} (id={self.tg_bot_info.get('id')})"
                    if self.tg_bot_info else "غیرفعال")
        return ("👤 هویت\n"
                f"▫️ شما (ادمین): {self._current_user_id}\n"
                f"▫️ سلف‌بات / حساب تلگرام: {tg_line}\n"
                f"▫️ بله: {bale_line}\n"
                f"▫️ بات مدیریت تلگرام: {bot_line}\n"
                f"▫️ پنل‌های فعال: {self._surfaces()}")

    async def cmd_access(self, platform, args, msg):
        """تست واقعی دسترسی هر حساب به کانال‌های هر جفت (ارسال/خواندن آزمایشی)."""
        from .wizard import probe_bale_access, probe_tg_access

        pairs = self.db.list_pairs()
        if not pairs:
            return "هنوز جفتی ثبت نشده — /add"
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            try:
                ok, note = await probe_tg_access(self.tg, p["tg_chat_id"])
            except Exception as e:
                note = f"✘ {str(e)[:60]}"
            lines.append(f"  ▫️ سلف تلگرام → {p['tg_label'] or p['tg_chat_id']}: {note}")
            try:
                ok, note = await probe_bale_access(self.bale, p["bale_chat_id"])
            except Exception as e:
                note = f"✘ {str(e)[:60]}"
            lines.append(f"  ▫️ سمت بله → {p['bale_label'] or p['bale_chat_id']}: {note}")
        return "\n".join(lines)

    async def cmd_promote(self, platform, args, msg):
        """سلف بله (ادمین کانال) ربات بله را به کانال‌ها اضافه و ادمین می‌کند."""
        from .bale_user import BaleUserAPI

        if not isinstance(self.bale, BaleUserAPI):
            return ("🛡 این کار با سلف بله انجام می‌شود — در حالت ربات ممکن نیست.\n"
                    "BALE_MODE=user کنید (یا از ویزارد تلگرام: 🛡 ادمین‌کردن ربات).")
        args = [a for a in (args or []) if a]
        pairs = self.db.list_pairs()
        if args and args[0].isdigit():
            pid = int(args[0])
            pairs = [p for p in pairs if p["id"] == pid] or pairs
            bot_ref = args[1] if len(args) > 1 else None
        else:
            bot_ref = args[0] if args else None
        if not pairs:
            return "هنوز جفتی ثبت نشده — /add"
        if not bot_ref:
            return ("یوزرنیم ربات بله را بدهید: /promote @my_bale_bot\n"
                    "(یا از ویزارد بات تلگرام: 🛡 ادمین‌کردن ربات)")
        lines = ["🛡 نتیجهٔ ادمین‌کردن:"]
        for p in pairs:
            label = p["bale_label"] or p["bale_chat_id"]
            try:
                await self.bale.add_admin(p["bale_chat_id"], bot_ref)
                lines.append(f"  ▫️ {label}: ✔ اضافه و ادمین شد")
            except Exception as e:
                lines.append(f"  ▫️ {label}: ✘ {str(e)[:100]}")
        return "\n".join(lines)

    async def cmd_dashboard(self, platform, args, msg):
        """نشانی + اعتبارنامهٔ داشبورد وب (رمز اولیه فقط یک بار نشان داده می‌شود)."""
        from .dashboard import Dashboard
        from .store import Store

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

    async def cmd_passwd(self, platform, args, msg):
        from .dashboard import Dashboard
        from .store import Store

        new = (args or [""])[0]
        if len(new) < 6:
            return "فرمت: /passwd <رمز_جدید> — حداقل ۶ کاراکتر"
        Dashboard.change_password(Store(self.db), new)
        return "✅ رمز داشبورد تغییر کرد."

    async def cmd_dashuser(self, platform, args, msg):
        from .dashboard import Dashboard
        from .store import Store

        user = (args or [""])[0]
        if not user or " " in user:
            return "فرمت: /dashuser <یوزرنیم>"
        Dashboard.change_user(Store(self.db), user)
        return f"✅ یوزرنیم داشبورد: {user}"

    async def cmd_setup(self, platform, args, msg):
        return ("🧙‍♂️ ویزارد نصب فقط در **بات مدیریت تلگرام** باز می‌شود: /setup\n"
                "(همه‌چیز بدون هیچ شناسه عددی همان‌جا ست می‌شود)")

    async def cmd_pause(self, platform, args, msg):
        self.bridge.paused = True
        self.db.set_meta("paused", "1")
        return ("⏸ همگام‌سازی متوقف شد.\n"
                "پیام‌های جدید تا زمان /resume منتقل نمی‌شوند (نگاشت‌های قبلی حفظ می‌شوند).")

    async def cmd_resume(self, platform, args, msg):
        self.bridge.paused = False
        self.db.set_meta("paused", "0")
        return "▶️ همگام‌سازی از سر گرفته شد."

    async def cmd_logs(self, platform, args, msg):
        if not self.log_buffer:
            return "لاگ در دسترس نیست."
        n = 15
        if args and args[0].isdigit():
            n = int(args[0])
        lines = self.log_buffer.tail(n)
        if not lines:
            return "هنوز لاگی ثبت نشده."
        return "📜 آخرین لاگ‌ها:\n" + "\n".join(lines)

    async def cmd_add(self, platform, args, msg):
        if len(args) < 2:
            return "فرمت: /add <کانال_تلگرام> <کانال_بله> [both|tg2bale|bale2tg]"
        tg_ref, bale_ref = args[0], args[1]
        mode = "both"
        if len(args) >= 3:
            mode = MODE_ALIASES.get(args[2].lower().replace("-", "_"))
            if not mode:
                return "حالت نامعتبر. یکی از: both ، tg2bale ، bale2tg"

        tg_id, tg_label, tg_username = await self._resolve_tg(tg_ref)
        bale_id, bale_label, bale_username = await self._resolve_bale(bale_ref)

        pair_id = self.db.add_pair(tg_id, tg_label, tg_username,
                                   bale_id, bale_label, bale_username, mode)
        return (f"✅ جفت #{pair_id} ثبت شد.\n"
                f"▫️ تلگرام: {tg_label or tg_username or tg_id}\n"
                f"▫️ بله: {bale_label or bale_username or bale_id}\n"
                f"▫️ جهت: {MODE_LABELS[mode]}\n\n"
                "دقت کنید: حساب تلگرام باید عضو کانال تلگرام باشد و ربات بله باید در کانال بله "
                "ادمین با دسترسی ارسال/ویرایش/حذف باشد.")

    async def cmd_remove(self, platform, args, msg):
        if not args:
            return "فرمت: /remove <شناسه جفت>"
        ok = self.db.remove_pair(int(args[0]))
        return "✅ جفت حذف شد." if ok else "چنین جفتی پیدا نشد."

    async def cmd_mode(self, platform, args, msg):
        if len(args) < 2:
            return "فرمت: /mode <شناسه جفت> <both|tg2bale|bale2tg>"
        mode = MODE_ALIASES.get(args[1].lower().replace("-", "_"))
        if not mode:
            return "حالت نامعتبر. یکی از: both ، tg2bale ، bale2tg"
        ok = self.db.set_mode(int(args[0]), mode)
        return f"✅ جهت جفت #{args[0]} → {MODE_LABELS[mode]}" if ok else "چنین جفتی پیدا نشد."

    async def cmd_list(self, platform, args, msg):
        pairs = self.db.list_pairs()
        if not pairs:
            return "هنوز جفتی ثبت نشده. با /add شروع کنید."
        lines = ["📋 جفت‌های متصل:", ""]
        for p in pairs:
            lines.append(
                f"#{p['id']} | {MODE_LABELS.get(p['mode'], p['mode'])}\n"
                f"   تلگرام: {p['tg_label'] or p['tg_username'] or p['tg_chat_id']}\n"
                f"   بله: {p['bale_label'] or p['bale_username'] or p['bale_chat_id']}"
            )
        return "\n".join(lines)

    async def cmd_test(self, platform, args, msg):
        if not args:
            return "فرمت: /test <شناسه جفت>"
        pair = self.db.get_pair(int(args[0]))
        if not pair:
            return "چنین جفتی پیدا نشد."
        text = f"✅ تست پل همگام‌سازی — جفت #{pair['id']}"
        done = []
        if pair["mode"] in ("tg2bale", "both"):
            try:
                await self.bale.send_message(pair["bale_chat_id"], text)
                done.append("بله ✔")
            except Exception as e:
                done.append(f"بله ✘ ({e})")
        if pair["mode"] in ("bale2tg", "both"):
            try:
                ent = await self.bridge._tg_entity(int(pair["tg_chat_id"]))
                m = await self.tg.send_message(ent, text)
                self.db.mark_sent("tg", str(pair["tg_chat_id"]), m.id)
                done.append("تلگرام ✔")
            except Exception as e:
                done.append(f"تلگرام ✘ ({e})")
        return "نتیجه تست: " + " | ".join(done)

    async def cmd_id(self, platform, args, msg):
        info = await self._describe_forward(platform, msg)
        return info or ("روی یک پیام فوروارد‌شده ریپلای کنید یا آن را فوروارد کنید "
                        "تا شناسه چت مبدأ را بگویم.")

    # ---------------------------------------------------------- شناسه‌ها
    async def _describe_forward(self, platform, msg) -> str | None:
        if not msg:
            return None
        try:
            if platform in ("bale", "tgbot"):
                chat = msg.get("forward_from_chat")
                user = msg.get("forward_from")
                origin = msg.get("forward_origin") or {}
                if not chat and origin.get("chat"):
                    chat = origin.get("chat")
                if not user and origin.get("sender_user"):
                    user = origin.get("sender_user")
                if not chat and not user and origin.get("sender_user_name"):
                    return f"ℹ️ فرستنده: {origin['sender_user_name']}"
                if chat:
                    uname = f"@{chat['username']}" if chat.get("username") else "—"
                    return (f"🆔 شناسه کانال مبدأ:\n"
                            f"▫️ نام: {chat.get('title') or uname}\n"
                            f"▫️ آیدی عددی: {chat['id']}\n"
                            f"▫️ یوزرنیم: {uname}\n\n"
                            f"مثال: /add <کانال_تلگرام> {chat['id']}")
                if user:
                    uname = f"@{user['username']}" if user.get("username") else "—"
                    return (f"🆔 شناسه کاربر مبدأ:\n▫️ آیدی عددی: {user['id']}\n"
                            f"▫️ یوزرنیم: {uname}")
                return None
            # تلگرام
            fwd = getattr(msg, "forward", None)
            if not fwd:
                return None
            from_id = getattr(fwd, "from_id", None)
            if from_id is None:
                return f"ℹ️ فرستنده: {getattr(fwd, 'from_name', 'ناشناس')}"
            marked = tg_utils.get_peer_id(from_id)
            uname = "—"
            try:
                ent = await self.tg.get_entity(from_id)
                if getattr(ent, "username", None):
                    uname = f"@{ent.username}"
            except Exception:
                ent = None
            title = getattr(ent, "title", None) or getattr(fwd, "from_name", None) or uname
            return (f"🆔 شناسه چت مبدأ تلگرام:\n"
                    f"▫️ نام: {title}\n"
                    f"▫️ آیدی عددی (با -100): {marked}\n"
                    f"▫️ یوزرنیم: {uname}\n\n"
                    f"مثال: /add {marked} <کانال_بله>")
        except Exception:
            log.exception("describe_forward failed")
            return None

    async def _resolve_tg(self, ref: str):
        ref = ref.strip()
        try:
            if re.fullmatch(r"-?\d+", ref):
                ent = await self.tg.get_entity(int(ref))
            else:
                ent = await self.tg.get_entity(ref)
        except Exception as e:
            raise ValueError(
                f"کانال تلگرام «{ref}» پیدا نشد ({e}). حساب باید عضو آن کانال باشد؛ "
                "شناسه عددی را با /id بگیرید."
            ) from e
        marked = tg_utils.get_peer_id(ent)
        label = getattr(ent, "title", None) or " ".join(
            x for x in [getattr(ent, "first_name", ""), getattr(ent, "last_name", "")] if x
        ) or ""
        username = getattr(ent, "username", "") or ""
        return int(marked), label, username

    async def _resolve_bale(self, ref: str):
        ref = ref.strip()
        if ref.isdigit() or (ref.startswith("-") and ref[1:].isdigit()):
            chat_id = ref
        elif ref.startswith("@"):
            chat_id = ref
        else:
            chat_id = "@" + ref
        try:
            chat = await self.bale.get_chat(chat_id)
        except Exception as e:
            raise ValueError(
                f"چت بله «{ref}» پیدا نشد ({e}). ربات بله باید در کانال/گروه عضو "
                "(ترجیحاً ادمین) باشد. برای کانال خصوصی، پیامی از آن را به ربات فوروارد "
                "کنید و آیدی عددی را بگیرید."
            ) from e
        username = (chat.get("username") or "").lstrip("@")
        label = chat.get("title") or chat.get("first_name") or username or ""
        return str(chat.get("id")), label, username


def _fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s_ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)
