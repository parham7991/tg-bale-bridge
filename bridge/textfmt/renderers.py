"""RenderersEngine — بازنمایی پیام‌های بدون معادل مستقیم: نظرسنجی، تاس، مکان، سرویس."""
from __future__ import annotations


class RenderersEngine:
    """متن‌های جانشین — همه با نگه‌داری خطا (پیام بد هرگز mirror را نیندازد)."""

    @staticmethod
    def render_tg_poll(msg) -> str:
        try:
            poll = msg.media.poll
            question = (getattr(getattr(poll, "question", None), "text", None)
                        or getattr(poll, "question", ""))
            if not isinstance(question, str):
                question = str(question)
            lines = [f"📊 نظرسنجی: {question}", ""]
            for i, ans in enumerate(poll.answers, 1):
                t = (getattr(getattr(ans, "text", None), "text", None)
                     or getattr(ans, "text", ""))
                lines.append(f"{i}️⃣ {t}")
            if getattr(poll, "multiple_choice", False):
                lines.append("\n(چند گزینه‌ای)")
            return "\n".join(lines)
        except Exception:
            return "📊 نظرسنجی تلگرام"

    @staticmethod
    def render_tg_dice(msg) -> str:
        try:
            emoji = getattr(msg.media, "emoticon", "🎲")
            return f"🎲 تاس ({emoji}): {getattr(msg.media, 'value', '?')}"
        except Exception:
            return "🎲 تاس"

    @staticmethod
    def render_tg_venue(msg) -> str:
        try:
            v = msg.media.venue
            title = getattr(v, "title", "")
            address = getattr(v, "address", "")
            return f"📍 {title}\n{address}"
        except Exception:
            return "📍 مکان"

    @staticmethod
    def render_tg_service(msg) -> str:
        action = getattr(msg, "action", None)
        name = type(action).__name__ if action else "سرویس"
        return f"ℹ️ پیام سرویس تلگرام ({name})"

    @staticmethod
    def render_unsupported_tg(msg) -> str:
        text = (msg.message or "").strip()
        return text or "📎 پیام پشتیبانی‌نشده از تلگرام"

    @staticmethod
    def render_unsupported_bale(m: dict) -> str:
        text = (m.get("text") or m.get("caption") or "").strip()
        return text or "📎 پیام پشتیبانی‌نشده از بله"


# توابع سطح ماژول — سطح عمومی همیشه‌سبز
def render_tg_poll(msg) -> str:
    return RenderersEngine.render_tg_poll(msg)


def render_tg_dice(msg) -> str:
    return RenderersEngine.render_tg_dice(msg)


def render_tg_venue(msg) -> str:
    return RenderersEngine.render_tg_venue(msg)


def render_tg_service(msg) -> str:
    return RenderersEngine.render_tg_service(msg)


def render_unsupported_tg(msg) -> str:
    return RenderersEngine.render_unsupported_tg(msg)


def render_unsupported_bale(m: dict) -> str:
    return RenderersEngine.render_unsupported_bale(m)
