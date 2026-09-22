"""PathsEngine — مسیرهای داده (پوشه‌ها ساخته می‌شوند: data، data/tmp)."""
from __future__ import annotations

import os
from pathlib import Path

# ریشهٔ ریپو = دو پوشه بالاتر از این فایل (bridge/appcfg/paths.py)
REPO_ROOT = Path(__file__).resolve().parents[2]


class PathsEngine:
    """ساخت مسیرهای پایه — همان رفتار قدیمی: mkdir برای data و tmp."""

    def __init__(self, env: dict | None = None, base_dir: Path | None = None) -> None:
        self.env = os.environ if env is None else env
        self.base_dir = Path(base_dir) if base_dir else REPO_ROOT

    def build(self) -> dict:
        base = self.base_dir
        data_dir = Path(self.env.get("DATA_DIR", str(base / "data"))).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = data_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return {
            "BASE_DIR": base,
            "DATA_DIR": data_dir,
            "TMP_DIR": tmp_dir,
            "DB_PATH": data_dir / "bridge.db",
            "SESSION_PATH": data_dir / "tg",  # telethon پسوند .session را اضافه می‌کند
        }
