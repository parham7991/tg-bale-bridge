"""CallEngine — قلب انتقال HTTP: retry، rate-limit (retry_after)، multipart/json.

منطق دقیقاً مثل قبل:
    • تا ۴ تلاش؛ خطای شبکه → دو بار با تأخیر فزاینده (۱٫۵s، ۳s)
    • ``retry_after`` سرور → خواب + ۰٫۵s و تلاش دوباره (تا ۳ بار)
    • مقدارهای dict/list داخل multipart به JSON تبدیل می‌شوند
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import aiohttp

from .types_map import build_url

logger = logging.getLogger("bridge.botapi.transport")

MAX_ATTEMPTS = 4
NETWORK_RETRIES = 2          # خطای شبکه: تلاش‌های ۱ و ۲ → تاخیر فزاینده
RATE_LIMIT_RETRIES = 3       # retry_after: تا تلاش ۳


class CallEngine:
    """فراخوانی یک متد Bot-API — مصرف‌کنندهٔ نشست مشترک."""

    def __init__(self, api) -> None:
        self.api = api           # خواندن زندهٔ base/token/session — قابل پچ در تست

    async def call(self, method: str, params: dict | None = None,
                   files: dict | None = None):
        """فراخوانی متد. ``files``: نام_فیلد → مسیر فایل (multipart)."""
        params = {k: v for k, v in (params or {}).items() if v is not None}
        session = await self.api._get_session()

        for attempt in range(MAX_ATTEMPTS):
            payload = await self._once(session, method, params, files, attempt)
            if payload is None:
                continue                      # خطای شبکه — یا ادامه یا raise شده
            if payload.get("ok"):
                return payload.get("result")

            desc = payload.get("description", "خطای ناشناخته بله")
            code = payload.get("error_code", 0)
            resp_params = payload.get("parameters") or {}
            retry_after = resp_params.get("retry_after")
            if retry_after and attempt < RATE_LIMIT_RETRIES:
                logger.warning("rate limit on %s — retry after %ss", method, retry_after)
                await asyncio.sleep(float(retry_after) + 0.5)
                continue
            raise BotAPIError(desc, code, resp_params)

        raise BotAPIError(f"{method} پس از چند تلاش ناموفق بود")

    async def _once(self, session, method, params, files, attempt) -> Optional[dict]:
        """یک تلاش HTTP؛ در خطای شبکه None یا استثنا برمی‌گرداند."""
        try:
            if files:
                form = aiohttp.FormData()
                for name, value in params.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    form.add_field(name, str(value))
                for name, path in (files or {}).items():
                    path = Path(path)
                    form.add_field(
                        name,
                        path.open("rb"),
                        filename=path.name,
                        content_type="application/octet-stream",
                    )
                async with session.post(build_url(self.api.base, self.api.token,
                                                  method), data=form) as resp:
                    return await resp.json(content_type=None)
            async with session.post(build_url(self.api.base, self.api.token, method),
                                    json=params) as resp:
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < NETWORK_RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
                return None
            raise BotAPIError(f"خطای شبکه در {method}: {e}") from e


class BotAPIError(Exception):
    def __init__(self, description: str, error_code: int = 0, parameters=None):
        super().__init__(description)
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}
