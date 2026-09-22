"""MenuEngine — منوی اصلی ویزارد: کیبورد شیشه‌ای + متن وضعیت نصب."""
from __future__ import annotations

from typing import Any


class MenuEngine:
    """ساخت کیبورد و متن منو — از فروشگاه و پیکربندی می‌خواند، به شبکه نمی‌زند."""

    def __init__(self, db: Any, cfg: Any, store: Any) -> None:
        self.db = db
        self.cfg = cfg
        self.store = store

    # ───────────────────────────── کیبورد ─────────────────────────────
    def kb(self) -> dict:
        tg_ok = self.store.has_tg(self.cfg)
        rows = [
            [
                {"text": ("📱 سلف تلگرام ") + ("✅" if tg_ok else "○"),
                 "callback_data": "wiz:tg"},
                {"text": ("🟡 سلف بله ") + ("✅" if self.store.bale_self() else "○"),
                 "callback_data": "wiz:bale"},
            ],
            [
                {"text": ("🤖 ربات بله ") + ("✅" if self.store.bale_bot() else "○"),
                 "callback_data": "wiz:bbot"},
                {"text": "🔗 جفت کانال‌ها", "callback_data": "wiz:pair"},
            ],
            [
                {"text": "📊 وضعیت نصب", "callback_data": "wiz:status"},
                {"text": "🛡 ادمین‌کردن ربات", "callback_data": "wiz:promote"},
                {"text": "🌐 داشبورد", "callback_data": "wiz:dash"},
            ],
            [
                {"text": "✅ اتمام و راه‌اندازی", "callback_data": "wiz:done"},
            ],
        ]
        return {"inline_keyboard": rows}

    # ───────────────────────────── متن ─────────────────────────────
    def text(self) -> str:
        s = self.store
        st = self.cfg
        bale_bot = s.bale_bot()
        bb_name = ("@" + bale_bot["me"].get("username")
                   if bale_bot and bale_bot.get("me", {}).get("username")
                   else None)
        lines = [
            "🧙‍♂️ *ویزارد نصب پل تلگرام ⇄ بله*",
            "",
            f"{'✅' if s.has_tg(st) else '○'} سلف تلگرام"
            f" — {('شماره ' + s.tg_self().get('phone', '?')) if s.tg_self() else 'تنظیم نشده'}",
            f"{'✅' if s.bale_self() else '○'} سلف بله"
            f" — {('شماره ' + s.bale_self().get('phone', '?')) if s.bale_self() else 'تنظیم نشده'}",
            f"{'✅' if bale_bot else '○'} ربات بله — {bb_name or 'تنظیم نشده'}",
            f"▫️ جفت‌های کانال: {len(self.db.list_pairs())}",
            "",
            "از دکمه‌ها استفاده کنید. برای جفت‌کردن، یک پیام از هر کانال",
            "را در همین چت **فوروارد** کنید یا @آیدی‌اش را بفرستید.",
        ]
        return "\n".join(lines)
