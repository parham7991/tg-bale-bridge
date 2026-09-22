"""پیکربندی برنامه — از فایل .env خوانده می‌شود."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = DATA_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bridge.db"
SESSION_PATH = DATA_DIR / "tg"  # telethon پسوند .session را اضافه می‌کند

# --- تلگرام ---
TG_API_ID = _int("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TG_PHONE = os.getenv("TG_PHONE", "").strip()

# --- بله ---
BALE_TOKEN = os.getenv("BALE_TOKEN", "").strip()
BALE_API_BASE = os.getenv("BALE_API_BASE", "https://tapi.bale.ai").rstrip("/")
ADMIN_BALE_ID = _int("ADMIN_BALE_ID")

# --- عمومی ---
ALBUM_DELAY = _float("ALBUM_DELAY", 0.9)
BALE_POLL_TIMEOUT = _int("BALE_POLL_TIMEOUT", 30) or 30

# محدودیت‌های API بله (مستندات docs.bale.ai)
MAX_BALE_UPLOAD = 50 * 1024 * 1024        # حداکثر آپلود فایل (multipart)
MAX_BALE_PHOTO = 10 * 1024 * 1024         # حداکثر آپلود عکس (multipart)
MAX_BALE_DOWNLOAD = 20 * 1024 * 1024      # حداکثر دانلود فایل (getFile)

LIMIT_TEXT = 4096
LIMIT_CAPTION = 4096
LIMIT_CAPTION_GROUP = 1024                 # کپشن InputMedia در sendMediaGroup


def validate() -> list[str]:
    """خطاهای پیکربندی را برمی‌گرداند."""
    problems = []
    if not TG_API_ID or not TG_API_HASH:
        problems.append("TG_API_ID / TG_API_HASH تنظیم نشده (از my.telegram.org بگیرید)")
    if not BALE_TOKEN:
        problems.append("BALE_TOKEN تنظیم نشده (از @botfather بله بگیرید)")
    return problems
