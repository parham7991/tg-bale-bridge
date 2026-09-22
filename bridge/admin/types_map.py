"""نگاشت‌ها، ثابت‌ها و پارس خالص پنل ادمین — بدون شبکه و بدون وضعیت.

نام‌های مستعار دستورات (فارسی/انگلیسی)، برچسب جهت‌ها، متن راهنما،
پارس دستور و قالب‌بندی مدت فعالیت.
"""
from __future__ import annotations

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


def parse_command(text: str):
    """متن → (نام دستور، آرگومان‌ها)؛ ``/cmd@bot`` هم پشتیبانی می‌شود."""
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


def fmt_duration(seconds: float) -> str:
    """ثانیه → «2d 3h 15m»."""
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


# نام تاریخی
_fmt_duration = fmt_duration
