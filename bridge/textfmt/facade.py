"""نمای ترکیب قالب‌بندی — re-export همهٔ توابع خالص هر موتور.

سطح عمومی دقیقاً مثل قبل: همه به‌صورت تابع ماژول‌سطح صدا زده می‌شوند
(``fmt.tg_text_to_bale(...)``, ``fmt.split_text(...)`` و …)؛ داخل، هر بخش به
موتور خودش تفویض می‌شود:

    types_map  → ثابت‌ها/الگوها/UTF-16   · splitting → truncate/split_text
    tg2bale    → موجودیت تلگرام ⇢ MD بله  · bale2tg   → MD بله ⇢ (متن، موجودیت)
    headers    → هدرهای باز‌ارسال          · renderers → جانشین‌های پیام خاص
"""
from __future__ import annotations

from .bale2tg import BaleToTgEngine, bale_text_to_tg
from .headers import HeadersEngine, bale_forward_header, tg_forward_header
from .renderers import (
    RenderersEngine,
    render_tg_dice,
    render_tg_poll,
    render_tg_service,
    render_tg_venue,
    render_unsupported_bale,
    render_unsupported_tg,
)
from .splitting import join_header, split_text, truncate
from .tg2bale import TgToBaleEngine, tg_text_to_bale
from .types_map import (
    LIMIT_CAPTION,
    LIMIT_TEXT,
    MD_PAT,
    utf16_index_map,
    utf16_len,
)

__all__ = [
    "LIMIT_TEXT", "LIMIT_CAPTION", "MD_PAT",
    "truncate", "split_text", "join_header",
    "tg_text_to_bale", "bale_text_to_tg",
    "tg_forward_header", "bale_forward_header",
    "render_tg_poll", "render_tg_dice", "render_tg_venue", "render_tg_service",
    "render_unsupported_tg", "render_unsupported_bale",
    "utf16_len", "utf16_index_map",
    "TgToBaleEngine", "BaleToTgEngine", "HeadersEngine", "RenderersEngine",
]
