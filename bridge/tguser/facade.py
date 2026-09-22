"""TgSelfBot — نمای سازگاری سلف تلگرام (ریشهٔ ترکیب موتورها).

استفادهٔ کلاسیک (از v2.7.0):
    bot = TgSelfBot(tg, bridge, admin, me.id); bot.register()

تابع ماژول‌سطح ``register`` هم دقیقاً مثل قبل کار می‌کند.
"""
from __future__ import annotations

from typing import Any

from .events import TgEventsEngine
from .routing import TgEventRouter


class TgSelfBot:
    """سلف تلگرام: رویدادها → روتر (پنل ذخیره‌شده‌ها / پل)."""

    def __init__(self, client: Any, bridge: Any, admin: Any = None,
                 my_tg_id: int = 0) -> None:
        self.client = client
        self.router = TgEventRouter(bridge, admin=admin, my_tg_id=my_tg_id)
        self.events = TgEventsEngine(self.router)

    def register(self) -> None:
        """ثبت هر سه هندلر روی کلاینت — هم‌رفتار تابع register قدیمی."""
        self.events.register(self.client)


def register(client: Any, bridge: Any, admin: Any, my_tg_id: int) -> None:
    """سازگاری کامل با امضای قدیمی ``bridge.tg_user.register``."""
    TgSelfBot(client, bridge, admin=admin, my_tg_id=my_tg_id).register()
