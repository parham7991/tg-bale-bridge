"""JsonKVEngine — لایهٔ JSON روی جدول meta دیتابیس.

    get → رمضگاری JSON با بازگشت به پیش‌فرض در مقدار خراب
    set → سریالایز JSON (فارسی خوانا) + ذخیره
    delete → خالی‌کردن مقدار (حذف نرم، مثل قبل)
"""
from __future__ import annotations

import json
from typing import Any


class JsonKVEngine:
    """پایهٔ ذخیره‌سازی — همهٔ دسترسی‌های سطح بالا روی همین سوارند."""

    def __init__(self, db) -> None:
        self.db = db            # فقط get_meta/set_meta لازم دارد

    def get(self, key: str, default: Any = None) -> Any:
        raw = self.db.get_meta(f"cfg:{key}")
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        self.db.set_meta(f"cfg:{key}", json.dumps(value, ensure_ascii=False))

    def delete(self, key: str) -> None:
        self.db.set_meta(f"cfg:{key}", "")
