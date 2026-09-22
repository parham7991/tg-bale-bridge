"""بستهٔ قالب‌بندی — تمام منطق تبدیل متن/موجودیت بین تلگرام و بله.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → ثابت‌ها: سقف‌ها، الگوی MD بله، ریاضی UTF-16
    splitting.py  → SplitEngine: truncate + split_text
    tg2bale.py    → TgToBaleEngine: موجودیت تلگرام → Markdown بله
    bale2tg.py    → BaleToTgEngine: Markdown بله → (متن، موجودیت)
    headers.py    → HeadersEngine: هدرهای باز‌ارسال دو سمت
    renderers.py  → RenderersEngine: نظرسنجی/تاس/مکان/سرویس/پشتیبانی‌نشده
    facade.py     → re-export همهٔ توابع — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/formatter.py`` شیم باز-صادرات است؛ ``from bridge import formatter
as fmt`` مثل قبل کار می‌کند.
"""
from .facade import (  # noqa: F401
    LIMIT_CAPTION,
    LIMIT_TEXT,
    BaleToTgEngine,
    HeadersEngine,
    RenderersEngine,
    TgToBaleEngine,
    bale_forward_header,
    bale_text_to_tg,
    join_header,
    render_tg_dice,
    render_tg_poll,
    render_tg_service,
    render_tg_venue,
    render_unsupported_bale,
    render_unsupported_tg,
    split_text,
    tg_forward_header,
    tg_text_to_bale,
    truncate,
    utf16_index_map,
    utf16_len,
)
from .version import VERSION

__all__ = [
    "LIMIT_TEXT", "LIMIT_CAPTION",
    "truncate", "split_text", "tg_text_to_bale", "bale_text_to_tg",
    "tg_forward_header", "bale_forward_header", "join_header",
    "render_tg_poll", "render_tg_dice", "render_tg_venue", "render_tg_service",
    "render_unsupported_tg", "render_unsupported_bale",
    "utf16_len", "utf16_index_map",
    "TgToBaleEngine", "BaleToTgEngine", "HeadersEngine", "RenderersEngine",
    "VERSION",
]
