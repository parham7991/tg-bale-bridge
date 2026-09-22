"""بستهٔ ویزارد نصب — تمام منطق نصب داخل بات مدیریت، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py → ثابت‌ها و استخراج‌های خالص (کیبورد جهت، فوروارد، توکن)
    menu.py      → MenuEngine: کیبورد + متن وضعیت منو
    accounts.py  → AccountsEngine: BotAPI سمت بله + بررسی توکن
    pairing.py   → PairingEngine: جفت‌کردن دومرحله‌ای کانال‌ها + جهت + ثبت
    checks.py    → AccessReportEngine: گزارش دسترسی واقعی همهٔ حساب‌ها
    promote.py   → PromoteEngine: ادمین‌کردن ربات بله توسط سلف
    dashinfo.py  → DashInfoEngine: نمایش آدرس/رمز داشبورد
    finish.py    → FinishEngine: پایان نصب + ری‌استارت خودکار
    probes.py    → توابع سازگاری پروب (برای ادمین/داشبورد/تست‌ها)
    facade.py    → Wizard: ریشهٔ ترکیب — ماشین حالت + تفویض

سازگاری: ``bridge/wizard.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.wizard`` در دسترس است.
"""
from .facade import Wizard
from .probes import _tg_username, probe_bale_access, probe_tg_access
from .version import VERSION

__all__ = [
    "Wizard", "probe_tg_access", "probe_bale_access", "_tg_username", "VERSION",
]
