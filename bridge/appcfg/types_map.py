"""ثابت‌های پیکربندی — محدودیت‌های API بله و سقف‌های متنی (از docs.bale.ai)."""
from __future__ import annotations

MAX_BALE_UPLOAD = 50 * 1024 * 1024        # حداکثر آپلود فایل (multipart)
MAX_BALE_PHOTO = 10 * 1024 * 1024         # حداکثر آپلود عکس (multipart)
MAX_BALE_DOWNLOAD = 20 * 1024 * 1024      # حداکثر دانلود فایل (getFile)

LIMIT_TEXT = 4096
LIMIT_CAPTION = 4096
LIMIT_CAPTION_GROUP = 1024                 # کپشن InputMedia در sendMediaGroup

BALE_MODES = ("bot", "user")
