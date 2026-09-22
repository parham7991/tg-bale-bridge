"""نگاشت‌ها و ثابت‌های خالص قالب‌بندی متن — سقف‌ها و الگوها.

    • سقف‌های متن/کپشن بله
    • الگوی Markdown بله (‎[متن](لینک) | *برجسته* | _کج_)
    • محاسبهٔ طول UTF-16 (تلگرام موجودیت‌ها را با واحد UTF-16 می‌شمارد)
"""
from __future__ import annotations

import re

# سقف‌های رندر
LIMIT_TEXT = 4096
LIMIT_CAPTION = 4096

# الگوی Markdown سادهٔ بله (به ترتیب: لینک، برجسته، کج)
MD_PAT = re.compile(
    r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)"   # [متن](لینک)
    r"|\*([^*\n]+)\*"                          # *برجسته*
    r"|_([^_\n]+)_"                            # _کج_
)

# هدر بازنشر
FORWARD_HEADER_TPL = "🔁 باز‌ارسال از: {}"

# نام تاریخی
_FW_TG = FORWARD_HEADER_TPL
_MD_PAT = MD_PAT


def utf16_len(text: str) -> int:
    """طول متن بر حسب واحد UTF-16 (ایموجی = ۲)."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def utf16_index_map(text: str) -> dict:
    """نگاشت اندیس UTF-16 (تلگرام) به اندیس پایتون."""
    mapping, u16 = {}, 0
    for i, ch in enumerate(text):
        mapping[u16] = i
        u16 += 2 if ord(ch) > 0xFFFF else 1
    mapping[u16] = len(text)
    return mapping


# نام‌های تاریخی
_utf16_len = utf16_len
_utf16_index_map = utf16_index_map
