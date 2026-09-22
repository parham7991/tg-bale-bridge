"""پروب‌های دسترسی و نرمال‌سازی — توابع ماژول‌سطح سازگار با نسخه‌های قبل.

منطق واقعی در دروازه‌های هر سمت است (``bridge/tguser`` و ``bridge/bale``)؛
این‌ها فقط پوشش سازگاری‌اند (ادمین/داشبورد/تست‌ها از همین‌جا import می‌کنند).
"""
from __future__ import annotations


def _tg_username(ref: str) -> str:
    """از دروازهٔ سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
    from ..tguser import TgSelfGateway

    return TgSelfGateway.normalize_username(ref)


async def probe_tg_access(tg_client, chat_id) -> tuple[bool, str]:
    """از دروازهٔ سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
    from ..tguser import TgSelfGateway

    return await TgSelfGateway.probe(tg_client, int(chat_id))


async def probe_bale_access(bale_api, chat_id) -> tuple[bool, str]:
    """از موتور gateway بله — همان منطق، یک‌جا نگهداری می‌شود."""
    from ..bale import BaleBotGateway

    return await BaleBotGateway.probe(bale_api, int(chat_id))
