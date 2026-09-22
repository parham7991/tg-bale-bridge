"""ثابت‌های بافر لاگ — ظرفیت پیش‌فرض، قالب خطوط و مرزهای tail."""
from __future__ import annotations

DEFAULT_CAPACITY = 300

LOG_FMT = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
DATE_FMT = "%H:%M:%S"

TAIL_MIN = 1
TAIL_MAX = 100
