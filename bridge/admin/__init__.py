"""بستهٔ پنل ادمین — تمام منطق دستورات مدیریتی، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py   → ثابت‌ها: نام‌های مستعار دستورات/جهت‌ها، راهنما، پارس، مدت فعالیت
    surfaces.py    → SurfacesEngine: پنل‌های فعال + حالت سلف/ربات
    resolver.py    → ResolverEngine: resolve تلگرام + توضیح فوروارد (هر سه شکل)
    pairs_cmds.py  → PairsCommandsEngine: add / remove / mode / list
    system_cmds.py → SystemCommandsEngine: status / whoami / logs
    control_cmds.py→ ControlCommandsEngine: pause / resume / test
    ops_cmds.py    → OpsCommandsEngine: access / promote
    dash_cmds.py   → DashCommandsEngine: dashboard / passwd / dashuser
    probes.py      → توابع سازگاری پروب
    facade.py      → Admin: احراز + dispatch + تفویض — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/admin.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.admin`` در دسترس است.
"""
from .facade import Admin
from .resolver import ResolverEngine
from .surfaces import SurfacesEngine
from .types_map import (  # noqa: F401 — نام‌های تاریخی بیرون استفاده می‌شوند
    CMD_ALIASES,
    HELP,
    MINIMAL_HELP,
    MODE_ALIASES,
    MODE_LABELS,
    _fmt_duration,
    fmt_duration,
    parse_command,
)
from .version import VERSION

__all__ = [
    "Admin", "SurfacesEngine", "ResolverEngine",
    "MODE_ALIASES", "MODE_LABELS", "CMD_ALIASES", "HELP", "MINIMAL_HELP",
    "parse_command", "fmt_duration", "_fmt_duration", "VERSION",
]
