"""نمای بستهٔ پیکربندی — بارگذاری کامل + تزریق در فضای‌نام ماژول config.

چرا populate؟ مصرف‌کننده‌ها «ماژول» config را mutate می‌کنند (مثلاً
OverridesEngine مقدار store را می‌ریزد داخل cfg). پس validate باید همان
فضای‌نامِ زندهٔ ماژول را بخواند — بستنِ (closure) روی dict ماژول این را
تضمین می‌کند.
"""
from __future__ import annotations

from dotenv import load_dotenv

from .envparse import EnvParseEngine
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


def load(env: dict | None = None, base_dir=None) -> dict:
    """بارگذاری کامل پیکربندی — dict تخت از همهٔ بخش‌ها + ثابت‌ها."""
    vals: dict = {}
    env = env if env is not None else dict(_loaded_env())
    vals.update(PathsEngine(env, base_dir).build())
    sec = SectionsEngine(env)
    vals.update(sec.tg())
    vals.update(sec.bale(vals["DATA_DIR"]))
    vals.update(sec.control())
    vals.update(sec.general())
    vals.update(sec.dash())
    vals.update({
        "MAX_BALE_UPLOAD": MAX_BALE_UPLOAD,
        "MAX_BALE_PHOTO": MAX_BALE_PHOTO,
        "MAX_BALE_DOWNLOAD": MAX_BALE_DOWNLOAD,
        "LIMIT_TEXT": LIMIT_TEXT,
        "LIMIT_CAPTION": LIMIT_CAPTION,
        "LIMIT_CAPTION_GROUP": LIMIT_CAPTION_GROUP,
    })
    return vals


def _loaded_env() -> dict:
    """.env ریشه را یک‌بار داخل os.environ می‌ریزد و os.environ را برمی‌گرداند."""
    load_dotenv(REPO_ROOT / ".env")
    import os
    return os.environ


def populate(ns: dict, env: dict | None = None) -> None:
    """مقادیر را در فضای‌نام ماژول config می‌ریزد + validate زنده می‌سازد."""
    ns.update(load(env))
    ns["validate"] = _make_validator(ns)


def _make_validator(ns: dict):
    def validate() -> list[str]:
        """خطاهای پیکربندی را برمی‌گرداند (مقادیر لحظه‌ای ماژول config)."""
        return ValidatorEngine().run(
            {name: ns.get(name) for name in ValidatorEngine.FIELDS})

    return validate


__all__ = ["load", "populate", "EnvParseEngine", "PathsEngine",
           "SectionsEngine", "ValidatorEngine", "REPO_ROOT"]
