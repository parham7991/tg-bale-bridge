"""توابع سازگاری پروب — ادمین قبلاً از wizard پروب می‌گرفت؛ همان امضا حفظ شده."""
from __future__ import annotations


async def probe_bale_access(bale_api, chat_id) -> tuple[bool, str]:
    """از موتور gateway بله — همان منطق، یک‌جا نگهداری می‌شود."""
    from ..bale import BaleBotGateway

    return await BaleBotGateway.probe(bale_api, int(chat_id))


async def probe_tg_access(tg_client, chat_id) -> tuple[bool, str]:
    """از دروازهٔ سلف تلگرام — همان منطق، یک‌جا نگهداری می‌شود."""
    from ..tguser import TgSelfGateway

    return await TgSelfGateway.probe(tg_client, int(chat_id))
