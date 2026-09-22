"""بستهٔ پیکربندی برنامه — خواندن .env، مسیرها، بخش‌ها و اعتبارسنجی.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → ثابت‌ها: محدودیت‌های API بله + سقف‌های متنی
    envparse.py   → EnvParseEngine: مکانیک int/float/flag روی env
    paths.py      → PathsEngine: BASE/DATA/TMP/DB/SESSION (+ mkdir)
    sections.py   → SectionsEngine: بخش‌های تلگرام/بله/کنترل/عمومی/داشبورد
    validator.py  → ValidatorEngine: فهرست مشکل‌های پیکربندی
    facade.py     → load() + populate() — تزریق در ماژول config با validate زنده

سازگاری: ``config.py`` شیم است — ``import config as cfg`` مثل قبل کار می‌کند.
"""
from .envparse import EnvParseEngine
from .facade import load, populate
from .paths import REPO_ROOT, PathsEngine
from .sections import SectionsEngine
from .types_map import (
                        LIMIT_CAPTION,
                        LIMIT_CAPTION_GROUP,
                        LIMIT_TEXT,
                        MAX_BALE_DOWNLOAD,
                        MAX_BALE_PHOTO,
                        MAX_BALE_UPLOAD,
)
from .validator import ValidatorEngine
from .version import VERSION

__all__ = ["load", "populate", "EnvParseEngine", "PathsEngine",
           "SectionsEngine", "ValidatorEngine", "REPO_ROOT",
           "MAX_BALE_UPLOAD", "MAX_BALE_PHOTO", "MAX_BALE_DOWNLOAD",
           "LIMIT_TEXT", "LIMIT_CAPTION", "LIMIT_CAPTION_GROUP", "VERSION"]
