"""ValidatorEngine — بررسی صحت پیکربندی؛ فهرست مشکل‌ها (فارسی) برمی‌گرداند."""
from __future__ import annotations

from pathlib import Path

from .types_map import BALE_MODES


class ValidatorEngine:
    """خالص و پارامتری — روی هر نگاشتی از مقادیر کار می‌کند."""

    FIELDS = ("TG_API_ID", "TG_API_HASH", "BALE_MODE", "BALE_TOKEN", "BALE_SESSION")

    def run(self, v: dict) -> list[str]:
        problems: list[str] = []
        if not v.get("TG_API_ID") or not v.get("TG_API_HASH"):
            problems.append("TG_API_ID / TG_API_HASH تنظیم نشده (از my.telegram.org بگیرید)")
        mode = v.get("BALE_MODE")
        if mode not in BALE_MODES:
            problems.append(f'BALE_MODE باید "bot" یا "user" باشد (الان: {mode!r})')
        if mode == "bot" and not v.get("BALE_TOKEN"):
            problems.append("BALE_TOKEN تنظیم نشده (از @botfather بله بگیرید)")
        if mode == "user":
            sess = Path(v.get("BALE_SESSION") or "")
            sess = sess if sess.suffix == ".bale" else sess.with_suffix(".bale")
            if not sess.exists():
                problems.append(
                    f"نشست سلف‌بات بله پیدا نشد ({sess}) — "
                    "ابتدا یک بار python login_bale.py را اجرا کنید"
                )
        return problems
