"""Bridge — نمای سازگاری موتور همگام‌سازی (ریشهٔ ترکیب بستهٔ transfer).

سطح عمومی دقیقاً مثل قبل:
    Bridge(tg, bale, db, cfg, my_tg_id, bale_bot)
    workers() · on_tg_new/edit/delete · on_bale_delete · queue_bale_msg/edit
    paused (خواندن/نوشتن) · bale_bot · استاتیک‌های _tg_kind/_bale_content

اما داخل، هر بخش به موتور خودش تفویض می‌شود:
    types_map → نگاشت‌های خالص   · loopguard → LoopGuard (لوپ/پژواک)
    albums    → AlbumCollector    · queueing → QueueEngine (صف‌ها/کارگرها)
    mirror_t2b → T2BEngine        · mirror_b2t → B2TEngine
    sync_edit → EditSyncEngine    · sync_delete → DeleteSyncEngine
"""
from __future__ import annotations

from .albums import AlbumCollector
from .loopguard import LoopGuard
from .mirror_b2t import B2TEngine
from .mirror_t2b import T2BEngine
from .queueing import QueueEngine
from .sync_delete import DeleteSyncEngine
from .sync_edit import EditSyncEngine
from .types_map import bale_content, build_entities, tg_kind


class Bridge:
    """موتور همگام‌سازی: تلگرام ⇄ بله (متن، رسانه، آلبوم، ویرایش، حذف)."""

    def __init__(self, tg, bale, db, cfg, my_tg_id: int, bale_bot: dict) -> None:
        self.tg = tg
        self.bale = bale
        self.db = db
        self.cfg = cfg
        self.my_tg_id = int(my_tg_id)
        self.bale_bot = bale_bot or {}
        # ── موتورها ──
        self.guard = LoopGuard(db)
        self.albums_tg = AlbumCollector(None, lambda: cfg.ALBUM_DELAY,
                                        lambda m: m.id)
        self.albums_bale = AlbumCollector(None, lambda: cfg.ALBUM_DELAY * 1.4,
                                          lambda x: x.get("message_id", 0))
        self.queue = QueueEngine(self.guard, self.albums_tg, self.albums_bale)
        self.t2b = T2BEngine(tg, bale, db, cfg)
        self.b2t = B2TEngine(tg, bale, db, cfg)
        self.edits = EditSyncEngine(tg, bale, db, cfg, self.t2b, self.b2t, self.guard)
        self.deletes = DeleteSyncEngine(tg, bale, db, self.guard)
        # سیم‌کشی صف‌ها به موتورها
        self.albums_tg.queue = self.queue.q_tg
        self.albums_bale.queue = self.queue.q_bale
        self.queue.tg_handlers = {"new": self.t2b.mirror,
                                  "edit": self.edits.process_tg_edit,
                                  "delete": self.deletes.process_tg_delete}
        self.queue.bale_handlers = {"new": self.b2t.mirror,
                                    "edit": self.edits.process_bale_edit,
                                    "delete": self.deletes.process_bale_delete}
        # ── سازگاری نام‌های قدیمی ──
        self.q_tg = self.queue.q_tg
        self.q_bale = self.queue.q_bale
        self._albums_tg = self.albums_tg.pending
        self._albums_bale = self.albums_bale.pending
        self._ignore_tg = self.guard.ignore_tg
        self._ignore_bale = self.guard.ignore_bale

    # ───────────────────────────── توقف/ادامه ─────────────────────────────
    @property
    def paused(self) -> bool:
        return self.queue.paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self.queue.paused = bool(value)

    # ───────────────────────────── چرخهٔ کار ─────────────────────────────
    def workers(self):
        return self.queue.workers()

    # ───────────────────────────── ورودی رویدادها ─────────────────────────────
    async def on_tg_new(self, msg) -> None:
        await self.queue.on_tg_new(msg)

    async def on_tg_edit(self, msg) -> None:
        await self.queue.on_tg_edit(msg)

    async def on_tg_delete(self, chat_id, deleted_ids) -> None:
        await self.queue.on_tg_delete(chat_id, deleted_ids)

    async def on_bale_delete(self, chat_id, deleted_ids) -> None:
        await self.queue.on_bale_delete(chat_id, deleted_ids)

    async def queue_bale_msg(self, m: dict) -> None:
        await self.queue.queue_bale_msg(m)

    async def queue_bale_edit(self, m: dict) -> None:
        await self.queue.queue_bale_edit(m)

    # ───────────────────────────── سازگاری سطح قبلی ─────────────────────────────
    _tg_kind = staticmethod(tg_kind)
    _bale_content = staticmethod(bale_content)
    _build_entities = staticmethod(build_entities)

    async def _process_tg_edit(self, msg) -> None:
        await self.edits.process_tg_edit(msg)

    async def _process_bale_edit(self, m) -> None:
        await self.edits.process_bale_edit(m)

    async def _process_tg_delete(self, chat_key, ids) -> None:
        await self.deletes.process_tg_delete(chat_key, ids)

    async def _process_bale_delete(self, chat_key, ids) -> None:
        await self.deletes.process_bale_delete(chat_key, ids)

    async def _mirror_tg(self, msgs) -> None:
        await self.t2b.mirror(msgs)

    async def _mirror_bale(self, msgs) -> None:
        await self.b2t.mirror(msgs)
