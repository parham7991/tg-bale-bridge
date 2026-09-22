"""BaleToTgEngine — Markdown بله → (متن خام، موجودیت‌های تلگرام).

خروجی entities: لیست (نوع، offset_پایتون، طول_پایتون، url) — آفست‌های پایتونی؛
تبدیل به UTF-16 بعداً در transfer/types_map.build_entities انجام می‌شود.
"""
from __future__ import annotations

from .types_map import MD_PAT


class BaleToTgEngine:
    """پارس Markdown سادهٔ بله — تابع خالص، بدون وضعیت."""

    @staticmethod
    def convert(text: str):
        """Markdown ساده بله را به (متن، موجودیت‌ها) تبدیل می‌کند."""
        if not text:
            return "", []
        parts, ents = [], []
        pos = 0
        cur_len = 0
        for m in MD_PAT.finditer(text):
            parts.append(text[pos:m.start()])
            cur_len += m.start() - pos
            if m.group(1) is not None:
                body, url = m.group(1), m.group(2)
                parts.append(body)
                ents.append(("text_link", cur_len, len(body), url))
            elif m.group(3) is not None:
                body = m.group(3)
                parts.append(body)
                ents.append(("bold", cur_len, len(body), None))
            else:
                body = m.group(4)
                parts.append(body)
                ents.append(("italic", cur_len, len(body), None))
            cur_len += len(body)
            pos = m.end()
        parts.append(text[pos:])
        return "".join(parts), ents


# تابع سطح ماژول — سطح عمومی همیشه‌سبز
def bale_text_to_tg(text: str):
    return BaleToTgEngine.convert(text)
