"""بستهٔ چرخهٔ اجرا — نقطهٔ شروع پل، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → بانر + تشخیص حالت نصاب
    overrides.py  → OverridesEngine: اعمال store روی cfg
    installer.py  → InstallerEngine: حالت نصاب (بات کنترل + ویزارد)
    wiring.py     → WiringEngine: سمت بله/تلگرام، پل+ادمین، داشبورد
    bots.py       → ControlBotsEngine: بات مدیریت + ربات بلهٔ ترکیبی
    lifecycle.py  → LifecycleEngine: صف وظایف + پاک‌سازی نهایی
    facade.py     → Runtime: جریان کامل — همان رفتار main قدیمی

سازگاری: ``main.py`` لانچر نازک مانده (execv ویزارد همچنان به همان فایل برمی‌گردد).
"""
from .facade import Runtime
from .overrides import OverridesEngine
from .version import VERSION

__all__ = ["Runtime", "OverridesEngine", "VERSION"]
