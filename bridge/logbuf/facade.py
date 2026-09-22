"""نمای بستهٔ بافر لاگ — همان سطح قدیمی ماژول logbuf.

قبل (ماژول تخت):  ``RingBufferHandler`` + ``install()``
حالا (بسته):      ring → handler → bootstrap  با facade که همان‌ها را صادر می‌کند.
"""
from __future__ import annotations

from .bootstrap import InstallEngine, install
from .handler import RingBufferHandler
from .ring import RingEngine
from .types_map import DATE_FMT, DEFAULT_CAPACITY, LOG_FMT, TAIL_MAX, TAIL_MIN
from .version import VERSION

__all__ = ["RingBufferHandler", "install", "InstallEngine", "RingEngine",
           "DEFAULT_CAPACITY", "LOG_FMT", "DATE_FMT", "TAIL_MIN", "TAIL_MAX",
           "VERSION"]
