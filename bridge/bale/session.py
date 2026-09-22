"""BaleSession — وضعیت مشترک سلف بله: کلاینت، دیسپچر، کش‌ها، چرخهٔ حیات.

همهٔ موتورها به یک نمونهٔ این کلاس دسترسی دارند؛ هیچ راز و کشی بیرون نمی‌رود.
تاریخ پیام‌ها و access_hash فایل‌ها در meta دیتابیس هم ماندگار می‌شوند تا بعد از
ری‌استارت هم حذف/دانلود کار کند.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from aiobale import Client, Dispatcher

logger = logging.getLogger("bridge.bale.session")


class BaleSession:
    """مالک کلاینت و کش‌ها — تنها نقطهٔ اشتراک بین موتورها."""

    def __init__(
        self,
        db: Any = None,
        client: Any = None,
        session_file: Optional[Any] = None,
        phone_number: Optional[str] = None,
        token: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.db = db
        # ── کش‌ها ──
        self.files: Dict[str, int] = {}          # file_id → access_hash
        self.dates: Dict[Tuple[int, int], int] = {}  # (chat, msg) → date
        self.chat_types: Dict[str, str] = {}     # chat_key → private|group|channel
        self.chat_meta: Dict[str, dict] = {}     # chat_key → {"id","type","title",...}
        self.id_cache: Dict[str, int] = {}       # @username → id
        # ── چرخهٔ حیات ──
        self.handler = None
        self.offset = 0
        self.started = False
        # ── کلاینت ──
        self.dp = Dispatcher()
        if client is not None:
            self.client = client
        else:
            kwargs: Dict[str, Any] = {"show_update_errors": True}
            if session_file is not None:
                kwargs["session_file"] = session_file
            if phone_number:
                kwargs["phone_number"] = phone_number
            if token:
                kwargs["token"] = token
            if user_agent:
                kwargs["user_agent"] = user_agent
            self.client = Client(self.dp, **kwargs)

    # ───────────────────────────── چرخهٔ حیات ─────────────────────────────
    async def start(self) -> None:
        """اتصال پس‌زمینه (start با run_in_background=True بلاک نمی‌کند)."""
        if self.started:
            return
        await self.client.start(run_in_background=True, signal_handling=False)
        self.started = True

    async def ensure_started(self) -> None:
        if not self.started:
            await self.start()

    async def stop(self) -> None:
        try:
            await self.client.stop()
        except Exception:
            pass
        self.started = False

    # ───────────────────────────── رویدادها ─────────────────────────────
    def bump(self) -> int:
        self.offset += 1
        return self.offset

    async def emit(self, upd: dict) -> None:
        if self.handler is None:
            return
        try:
            await self.handler(upd, self.bump())
        except Exception:
            logger.exception("bale-user handler error")

    # ───────────────────────────── کش تاریخ پیام‌ها ─────────────────────────────
    def remember_date(self, chat_id: Any, msg_id: Any, date: Any) -> None:
        try:
            d = int(date or 0)
        except (TypeError, ValueError):
            d = 0
        self.dates[(int(chat_id), int(msg_id))] = d
        if self.db is not None and d:
            try:
                self.db.set_meta(f"bdate:{int(chat_id)}:{int(msg_id)}", str(d))
            except Exception:
                pass

    def date_for(self, chat_id: Any, msg_id: Any) -> int:
        d = self.dates.get((int(chat_id), int(msg_id)))
        if d is None and self.db is not None:
            try:
                raw = self.db.get_meta(f"bdate:{int(chat_id)}:{int(msg_id)}")
                d = int(raw) if raw else 0
                self.dates[(int(chat_id), int(msg_id))] = d
            except Exception:
                d = 0
        return int(d or 0)

    # ───────────────────────────── کش فایل‌ها ─────────────────────────────
    def remember_file(self, file_id: Any, access_hash: Any) -> None:
        if file_id is None:
            return
        try:
            self.files[str(file_id)] = int(access_hash or 0)
        except (TypeError, ValueError):
            self.files[str(file_id)] = 0
        if self.db is not None:
            try:
                self.db.set_meta(f"bhash:{file_id}", str(int(access_hash or 0)))
            except Exception:
                pass

    def access_hash_for(self, file_id: Any) -> Optional[int]:
        h = self.files.get(str(file_id))
        if h is None and self.db is not None:
            try:
                raw = self.db.get_meta(f"bhash:{file_id}")
                h = int(raw) if raw else None
                if h is not None:
                    self.files[str(file_id)] = h
            except Exception:
                h = None
        return h

    # ───────────────────────────── متادیتای چت‌ها ─────────────────────────────
    def chat_type_of(self, chat_id: Any) -> str:
        return self.chat_types.get(str(chat_id), "group")

    def note_chat(self, chat_id: Any, info: dict) -> None:
        """ثبت/به‌روزرسانی متادیتای چت از یک دیکشنری Bot-API مانند."""
        meta = self.chat_meta.setdefault(str(chat_id), {"id": chat_id})
        meta.update({k: v for k, v in info.items() if v})
        meta["id"] = chat_id
        meta["type"] = info.get("type") or meta.get("type") or "private"
        self.chat_types[str(chat_id)] = meta["type"]

    def snapshot_result(self, chat_id: Any, msg: Any) -> dict:
        """نتیجهٔ استاندارد ارسال + ثبت تاریخ پیام تازه."""
        if isinstance(msg, list):
            msg = msg[-1] if msg else None
        if msg is None:
            return {"message_id": 0, "ok": True}
        mid = int(getattr(msg, "message_id", 0) or 0)
        self.remember_date(int(chat_id), mid, getattr(msg, "date", 0))
        return {"message_id": mid, "ok": True}

    @staticmethod
    def session_path(session_file: Any) -> Path:
        p = Path(str(session_file))
        return p if p.suffix == ".bale" else p.with_suffix(".bale")
