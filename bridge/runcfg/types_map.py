"""نگاشت‌ها و ثابت‌های خالص نگارخانهٔ تنظیمات — بدون منطق اجرایی.

همهٔ کلیدها با پیشوند ``cfg:`` در جدول meta ذخیره می‌شوند؛ مقدارها JSON‌اند
(با ensure_ascii=False تا فارسی خوانا بماند).
"""
from __future__ import annotations

PREFIX = "cfg:"


def key_of(key: str) -> str:
    """کلید کاربر → کلید واقعی جدول meta."""
    return f"{PREFIX}{key}"


def admin_id_from(value) -> int:
    """مقدار ذخیره‌شدهٔ ادمین → شناسه عددی (هم شکل dict، هم int)."""
    if isinstance(value, dict):
        return int(value.get("id") or 0)
    return int(value or 0)
