"""InstallEngine — نصب هندلر روی لاگر ریشه (قالب + سطح، مثل قبل)."""
from __future__ import annotations

import logging

from .handler import RingBufferHandler
from .types_map import DATE_FMT, DEFAULT_CAPACITY, LOG_FMT


class InstallEngine:
    """یک هندلر بسازد، قالب بدهد و به ریشه وصل کند."""

    @staticmethod
    def install(capacity: int = DEFAULT_CAPACITY,
                level: int = logging.INFO) -> RingBufferHandler:
        handler = RingBufferHandler(capacity)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(LOG_FMT, datefmt=DATE_FMT))
        logging.getLogger().addHandler(handler)
        return handler


install = InstallEngine.install  # noqa: E305  (سطح همان تابع قدیمی)
