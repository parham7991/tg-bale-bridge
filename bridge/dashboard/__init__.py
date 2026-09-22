"""بستهٔ داشبورد وب — هر بخش، یک ماژول و یک موتور مستقل.

معماری:
    app.py       → نقطهٔ مونتاژ: کلاس Dashboard + ساخت aiohttp Application
    api.py       → لایهٔ HTTP نازک: میدلور (auth/CSRF/خطا) + هندلرهای مسیرها
    auth.py      → موتور احراز هویت: PBKDF2، سشن‌ها، قفل تلاش ناموفق
    context.py   → RuntimeCtx: دسترسی تایپ‌شده به وضعیت زندهٔ پل
    engines/     → موتورهای دامنه‌ای (بدون HTTP):
                    status  → اسنپ‌شات وضعیت کل پل
                    pairs   → CRUD جفت‌های کانال + resolve واقعی
                    control → توقف/ادامهٔ سراسری
                    logs    → دمِ لاگ زنده
                    ops     → پروب دسترسی + ادمین‌کردن ربات توسط سلف
"""
from .app import Dashboard
from .auth import AuthEngine
from .version import VERSION

__all__ = ["Dashboard", "AuthEngine", "VERSION"]
