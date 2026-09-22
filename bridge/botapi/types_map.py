"""نگاشت‌ها و کمک‌تابع‌های خالص کلاینت Bot-API — بدون شبکه و بدون وضعیت.

ساخت نشانی متدها و فایل‌ها، جدول متدهای رسانه و ساخت payload آلبوم (media group).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

BASE_DEFAULT = "https://tapi.bale.ai"

# نوع رسانه → (متد Bot-API، نام فیلد multipart)
MEDIA_METHODS = {
    "photo": ("sendPhoto", "photo"),
    "video": ("sendVideo", "video"),
    "animation": ("sendAnimation", "animation"),
    "audio": ("sendAudio", "audio"),
    "voice": ("sendVoice", "voice"),
    "document": ("sendDocument", "document"),
    "sticker": ("sendSticker", "sticker"),
    "video_note": ("sendVideoNote", "video_note"),
}

# سقف کپشن در sendMediaGroup (مستندات بله)
MEDIA_GROUP_CAPTION_MAX = 1024


def normalize_base(base: str) -> str:
    """حذف اسلش انتهایی پایهٔ API."""
    return (base or BASE_DEFAULT).rstrip("/")


def build_url(base: str, token: str, method: str) -> str:
    return f"{base}/bot{token}/{method}"


def build_file_url(base: str, token: str, file_path: str) -> str:
    return f"{base}/file/bot{token}/{file_path}"


def build_media_group(
    items: List[Tuple[str, Any, str | None]],
) -> Tuple[Dict[str, Any], List[dict]]:
    """items (نوع، مسیر، کپشن) → (فایل‌های multipart، آرگومان media).

    هر آیتم به‌صورت ``attach://fN`` پیوند می‌خورد؛ کپشن به سقف ۱۰۲۴ بریده می‌شود.
    """
    form_files: Dict[str, Any] = {}
    media: List[dict] = []
    for i, (mtype, path, caption) in enumerate(items):
        name = f"f{i}"
        form_files[name] = path
        media.append({
            "type": mtype,
            "media": f"attach://{name}",
            "caption": (caption or "")[:MEDIA_GROUP_CAPTION_MAX] or None,
        })
    return form_files, media
