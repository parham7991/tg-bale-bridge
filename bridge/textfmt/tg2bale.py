"""TgToBaleEngine — موجودیت‌های تلگرام → Markdown بله.

فقط Bold/Italic/Link پشتیبانی می‌شود (بقیه به متن ساده می‌رسند)؛ آفست‌های
UTF-16 تلگرام با جدول نگاشت به اندیس پایتون برگردانده می‌شوند؛ همپوشانی
موجودیت‌ها با اولویتِ بیرونی‌ترین رندر می‌شود.
"""
from __future__ import annotations

from .types_map import utf16_index_map

# کلاس موجودیت تلگرام → تگ داخلی
_SUPPORTED = {
    "MessageEntityBold": "bold",
    "MessageEntityItalic": "italic",
    "MessageEntityTextUrl": "url",
    "MessageEntityUrl": "url",
}


class TgToBaleEngine:
    """ترجمهٔ قالب تلگرام به Markdown بله — تابع خالص، بدون وضعیت."""

    @staticmethod
    def convert(text: str, entities=None) -> str:
        """متن تلگرام را با Bold/Italic/Link به Markdown بله تبدیل می‌کند.

        بله همه متن‌ها را Markdown رندر می‌کند: *برجسته*، _کج_، [متن](لینک).
        """
        if not text:
            return ""
        if not entities:
            return text

        m = utf16_index_map(text)
        spans = []
        for e in entities:
            start = m.get(e.offset)
            end = m.get(e.offset + e.length)
            if start is None or end is None or end <= start:
                continue
            tag = _SUPPORTED.get(type(e).__name__)
            if not tag:
                continue
            url = getattr(e, "url", None) if tag == "url" else None
            spans.append((start, end, tag, url))

        if not spans:
            return text

        spans.sort(key=lambda s: (s[0], -s[1]))
        out, cursor = [], 0
        for start, end, tag, url in spans:
            if start < cursor:  # همپوشانی — از قالب‌بندی داخلی صرف‌نظر می‌کنیم
                continue
            out.append(text[cursor:start])
            chunk = text[start:end]
            if tag == "bold":
                out.append(f"*{chunk}*")
            elif tag == "italic":
                out.append(f"_{chunk}_")
            elif tag == "url":
                if chunk.strip().startswith("http"):
                    out.append(chunk)
                else:
                    out.append(f"[{chunk}]({url})" if url else chunk)
            cursor = end
        out.append(text[cursor:])
        return "".join(out)


# تابع سطح ماژول — سطح عمومی همیشه‌سبز
def tg_text_to_bale(text: str, entities=None) -> str:
    return TgToBaleEngine.convert(text, entities)
