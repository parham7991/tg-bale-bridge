"""بستهٔ بافر لاگ — نگهداری آخرین خطوط لاگ در حافظه (/logs و داشبورد).

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → ظرفیت پیش‌فرض، قالب خط، مرزهای tail
    ring.py       → RingEngine: حلقهٔ خالص خطوط (deque + clamp)
    handler.py    → HandlerEngine: RingBufferHandler امن روی RingEngine
    bootstrap.py  → InstallEngine: نصب روی لاگر ریشه با قالب استاندارد
    facade.py     → صادر کردن همان سطح قدیمی: RingBufferHandler + install

سازگاری: ``from ..logbuf import install`` مثل قبل کار می‌کند — بسته به‌جای
ماژول تخت قدیمی نشسته و هیچ شیم جداگانه‌ای لازم نیست.
"""
from .facade import (
                     DATE_FMT,
                     DEFAULT_CAPACITY,
                     LOG_FMT,
                     TAIL_MAX,
                     TAIL_MIN,
                     VERSION,
                     InstallEngine,
                     RingBufferHandler,
                     RingEngine,
                     install,
)

__all__ = ["RingBufferHandler", "install", "InstallEngine", "RingEngine",
           "DEFAULT_CAPACITY", "LOG_FMT", "DATE_FMT", "TAIL_MIN", "TAIL_MAX",
           "VERSION"]
