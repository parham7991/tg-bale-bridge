"""SCHEMA و ثابت‌های خالص لایهٔ داده — بدون منطق اجرایی.

جدول‌ها:
    pairs   → جفت‌های کانال (تلگرام ⇄ بله) با جهت همگام‌سازی
    msg_map → نقشهٔ پیام‌ها (برای ریپلای/ویرایش/حذف) با دو ایندکس دوطرفه
    sent    → دفترچهٔ «توسط پل فرستاده شد» (لایهٔ ۱ ضدلوپ، یک‌بارمصرف)
    sent_fp → اثر انگشت محتوا در پنجرهٔ زمانی (لایهٔ ۲ ضدلوپ)
    meta    → کلید/مقدار عمومی (آفست‌ها، pause، اکانت‌ها، …)
"""
from __future__ import annotations

SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_chat_id    INTEGER NOT NULL,
    tg_label      TEXT DEFAULT '',
    tg_username   TEXT DEFAULT '',
    bale_chat_id  TEXT NOT NULL,
    bale_label    TEXT DEFAULT '',
    bale_username TEXT DEFAULT '',
    mode          TEXT NOT NULL DEFAULT 'both',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS msg_map (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id     INTEGER NOT NULL,
    src_platform TEXT NOT NULL, src_chat TEXT NOT NULL, src_msg INTEGER NOT NULL,
    dst_platform TEXT NOT NULL, dst_chat TEXT NOT NULL, dst_msg INTEGER NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_map_src ON msg_map (src_platform, src_chat, src_msg);
CREATE INDEX IF NOT EXISTS idx_map_dst ON msg_map (dst_platform, dst_chat, dst_msg);

CREATE TABLE IF NOT EXISTS sent (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    chat       TEXT NOT NULL,
    msg        INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent ON sent (platform, chat, msg);

CREATE TABLE IF NOT EXISTS sent_fp (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    chat       TEXT NOT NULL,
    fp         TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fp ON sent_fp (platform, chat, fp);

CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

VALID_MODES = ("tg2bale", "bale2tg", "both")

# عمر پیش‌فرض کش‌های ضدلوپ: ۲ روز
CACHE_MAX_AGE = 2 * 24 * 3600
