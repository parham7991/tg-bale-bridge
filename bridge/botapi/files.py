"""FilesEngine — getFile + دانلود استریمی فایل به مسیر مقصد."""
from __future__ import annotations

import logging
from pathlib import Path

from .transport import BotAPIError

logger = logging.getLogger("bridge.botapi.files")

CHUNK = 1 << 16               # 64KB


class FilesEngine:
    """دانلود فایل از سرور — از نشست مشترک و file_url."""

    def __init__(self, api) -> None:
        self.api = api

    async def get_file(self, file_id: str):
        return await self.api.call("getFile", {"file_id": file_id})

    async def download_file(self, file_id: str, dest: Path) -> Path:
        info = await self.api.get_file(file_id)
        file_path = info.get("file_path")
        if not file_path:
            raise BotAPIError("file_path در پاسخ getFile نبود")
        session = await self.api._get_session()
        dest = Path(dest)
        async with session.get(self.api.file_url(file_path)) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK):
                    f.write(chunk)
        return dest
