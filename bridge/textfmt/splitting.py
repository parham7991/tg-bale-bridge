"""SplitEngine — بریدن و تراشیدن متن به سقف پلتفرم‌ها.

    truncate    → برش با سه‌نقطه
    split_text  → شکستن چندپیامی: اول سعی بر مرز خط، بعد برش سخت
"""
from __future__ import annotations

from .types_map import LIMIT_TEXT


def truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def join_header(header: str, body: str) -> str:
    """هدر + بدنه در یک پیام — بدنهٔ خالی فقط هدر می‌ماند."""
    body = body or ""
    if not header:
        return body
    return f"{header}\n{body}" if body.strip() else header


def split_text(text: str, limit: int = LIMIT_TEXT) -> list[str]:
    """متن بلند → تکه‌های ≤ limit (اول مرز خط، بعد برش سخت خطوط خیلی بلند)."""
    if len(text) <= limit:
        return [text]
    parts, buf = [], []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > limit and buf:
            parts.append("".join(buf))
            buf, size = [], 0
        if len(line) > limit:
            for i in range(0, len(line), limit):
                parts.append(line[i:i + limit])
            continue
        buf.append(line)
        size += len(line)
    if buf:
        parts.append("".join(buf))
    return parts or [""]
