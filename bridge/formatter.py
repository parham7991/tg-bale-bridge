"""تبدیل متن و موجودیت‌ها بین تلگرام و بله + بازنمایی پیام‌های خاص."""
from __future__ import annotations

import re

LIMIT_TEXT = 4096
LIMIT_CAPTION = 4096

_FW_TG = "🔁 باز‌ارسال از: {}"


# ---------------------------------------------------------------- کمکی
def truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def split_text(text: str, limit: int = LIMIT_TEXT) -> list[str]:
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


def _utf16_len(text: str) -> int:
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def _utf16_index_map(text: str) -> dict:
    """نگاشت اندیس UTF-16 (تلگرام) به اندیس پایتون."""
    mapping, u16 = {}, 0
    for i, ch in enumerate(text):
        mapping[u16] = i
        u16 += 2 if ord(ch) > 0xFFFF else 1
    mapping[u16] = len(text)
    return mapping


# ------------------------------------------------- تلگرام -> بله (Markdown بله)
def tg_text_to_bale(text: str, entities=None) -> str:
    """متن تلگرام را با Bold/Italic/Link به Markdown بله تبدیل می‌کند.

    بله همه متن‌ها را Markdown رندر می‌کند: *برجسته*، _کج_، [متن](لینک).
    """
    if not text:
        return ""
    if not entities:
        return text

    m = _utf16_index_map(text)
    spans = []
    for e in entities:
        start = m.get(e.offset)
        end = m.get(e.offset + e.length)
        if start is None or end is None or end <= start:
            continue
        etype = type(e).__name__
        tag = None
        url = None
        if etype == "MessageEntityBold":
            tag = "bold"
        elif etype == "MessageEntityItalic":
            tag = "italic"
        elif etype == "MessageEntityTextUrl":
            tag, url = "url", getattr(e, "url", None)
        elif etype == "MessageEntityUrl":
            tag = "url"
        if tag:
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
            if url and not chunk.strip().startswith("http"):
                out.append(f"[{chunk}]({url})")
            elif chunk.strip().startswith("http"):
                out.append(chunk)
            else:
                out.append(f"[{chunk}]({url})" if url else chunk)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


# ------------------------------------------------- بله -> تلگرام (Markdown بله)
_MD_PAT = re.compile(
    r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)"  # [متن](لینک)
    r"|\*([^*\n]+)\*"                        # *برجسته*
    r"|_([^_\n]+)_"                          # _کج_
)


def bale_text_to_tg(text: str):
    """Markdown ساده بله را به (متن، موجودیت‌ها) تبدیل می‌کند.

    خروجی entities: لیست (نوع، offset_پایتون، طول_پایتون، url).
    """
    if not text:
        return "", []
    parts, ents = [], []
    pos = 0
    cur_len = 0
    for m in _MD_PAT.finditer(text):
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


# ------------------------------------------------- هدر فوروارد
async def tg_forward_header(msg, client) -> str:
    fwd = getattr(msg, "forward", None)
    if not fwd:
        return ""
    name = getattr(fwd, "from_name", None)
    if not name:
        from_id = getattr(fwd, "from_id", None)
        try:
            if from_id is not None:
                ent = await client.get_entity(from_id)
                name = getattr(ent, "title", None) or " ".join(
                    x for x in [getattr(ent, "first_name", ""), getattr(ent, "last_name", "")] if x
                )
        except Exception:
            name = None
    if not name and getattr(fwd, "post_author", None):
        name = fwd.post_author
    return _FW_TG.format(name or "ناشناس")


def bale_forward_header(m: dict) -> str:
    chat = m.get("forward_from_chat")
    if chat:
        name = chat.get("title") or ("@" + chat["username"] if chat.get("username") else None)
        return _FW_TG.format(name or "ناشناس")
    user = m.get("forward_from")
    if user:
        name = " ".join(
            x for x in [user.get("first_name") or "", user.get("last_name") or ""] if x
        ).strip()
        return _FW_TG.format(name or user.get("username") or "ناشناس")
    return ""


# ------------------------------------------------- بازنمایی پیام‌های بدون معادل
def join_header(header: str, body: str) -> str:
    body = body or ""
    if not header:
        return body
    return f"{header}\n{body}" if body.strip() else header


def render_tg_poll(msg) -> str:
    try:
        poll = msg.media.poll
        question = (getattr(getattr(poll, "question", None), "text", None)
                    or getattr(poll, "question", ""))
        if not isinstance(question, str):
            question = str(question)
        lines = [f"📊 نظرسنجی: {question}", ""]
        for i, ans in enumerate(poll.answers, 1):
            t = getattr(getattr(ans, "text", None), "text", None) or getattr(ans, "text", "")
            lines.append(f"{i}️⃣ {t}")
        if getattr(poll, "multiple_choice", False):
            lines.append("\n(چند گزینه‌ای)")
        return "\n".join(lines)
    except Exception:
        return "📊 نظرسنجی تلگرام"


def render_tg_dice(msg) -> str:
    try:
        emoji = getattr(msg.media, "emoticon", "🎲")
        return f"🎲 تاس ({emoji}): {getattr(msg.media, 'value', '?')}"
    except Exception:
        return "🎲 تاس"


def render_tg_venue(msg) -> str:
    try:
        v = msg.media.venue
        title = getattr(v, "title", "")
        address = getattr(v, "address", "")
        return f"📍 {title}\n{address}"
    except Exception:
        return "📍 مکان"


def render_tg_service(msg) -> str:
    action = getattr(msg, "action", None)
    name = type(action).__name__ if action else "سرویس"
    return f"ℹ️ پیام سرویس تلگرام ({name})"


def render_unsupported_tg(msg) -> str:
    text = (msg.message or "").strip()
    return text or "📎 پیام پشتیبانی‌نشده از تلگرام"


def render_unsupported_bale(m: dict) -> str:
    text = (m.get("text") or m.get("caption") or "").strip()
    return text or "📎 پیام پشتیبانی‌نشده از بله"
