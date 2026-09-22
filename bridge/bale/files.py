"""FilesEngine — دانلود و متادیتای فایل با کش access_hash (ماندگار در meta)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Union

from ..bot_api import BotAPIError
from .session import BaleSession

logger = logging.getLogger("bridge.bale.files")


class FilesEngine:
    def __init__(self, session: BaleSession) -> None:
        self.s = session

    async def download_file(self, file_id: Any, dest: Union[str, Path],
                            **kw: Any) -> Union[str, Path]:
        h = self.s.access_hash_for(file_id)
        if h is None:
            raise BotAPIError(f"no access_hash cached for file {file_id!r}")
        try:
            await self.s.ensure_started()
            await self.s.client.download_file(
                file_id=int(file_id), access_hash=int(h), destination=str(dest), seek=True)
            return dest
        except Exception as exc:
            raise BotAPIError(f"download_file failed: {exc}") from exc

    async def get_file(self, file_id: Any, **kw: Any) -> dict:
        h = self.s.access_hash_for(file_id)
        if h is None:
            raise BotAPIError(f"no access_hash cached for file {file_id!r}")
        return {"file_id": str(file_id), "ok": True, "_access_hash": h}
