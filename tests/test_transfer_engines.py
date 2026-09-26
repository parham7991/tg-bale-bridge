"""تست‌های بستهٔ همگام‌سازی (bridge/transfer) — موتورهای صف/آلبوم/نگهبان لوپ."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from bridge.transfer import Bridge
from bridge.transfer.albums import AlbumCollector
from bridge.transfer.loopguard import LoopGuard
from bridge.transfer.queueing import QueueEngine
from bridge.transfer.types_map import bale_content, build_entities, fingerprint
from tests.conftest import run

# ───────────────────────────── LoopGuard ─────────────────────────────

class FakeDB:
    def __init__(self):
        self.sent = set()

    def was_sent(self, platform, chat, mid):
        return (platform, str(chat), mid) in self.sent

    def mark_sent(self, platform, chat, mid):
        self.sent.add((platform, str(chat), mid))

    def check_fp(self, *a, **k):
        return False

    def add_fp(self, *a, **k):
        pass


def test_guard_seen_mark():
    g = LoopGuard(FakeDB())
    assert not g.seen("tg", "-100", 5)
    g.mark("tg", "-100", 5)
    assert g.seen("tg", "-100", 5)
    assert g.seen("tg", -100, 5)          # str/int هم‌ارز


def test_guard_suppress_consume_release():
    g = LoopGuard(FakeDB())
    g.suppress("tg", "-100", 7)
    g.suppress("bale", "-200", 8)
    assert g.consume("tg", "-100", 7)     # پژواک → بلعیده شد
    assert not g.consume("tg", "-100", 7) # فقط یک‌بار
    assert g.consume("bale", -200, 8)     # int هم ببلعد
    g.suppress("tg", 1, 1)
    g.release("tg", 1, 1)
    assert not g.consume("tg", 1, 1)


def test_guard_sets_are_shared_with_facade():
    g = LoopGuard(FakeDB())
    g.suppress("tg", "c", 1)
    assert ("c", 1) in g.ignore_tg and not g.ignore_bale


# ───────────────────────────── AlbumCollector ─────────────────────────────

def test_album_collects_then_flushes_sorted():
    async def body():
        q = asyncio.Queue()
        alb = AlbumCollector(q, lambda: 0.01, lambda m: m["id"])
        for i in (3, 1, 2):
            alb.feed(("c", "g1"), {"id": i})
        await asyncio.sleep(0.05)
        kind, msgs = q.get_nowait()
        assert kind == "new" and [m["id"] for m in msgs] == [1, 2, 3]
        assert not alb.pending and not alb.tasks
    run(body())


def test_album_empty_flush_is_noop():
    async def body():
        q = asyncio.Queue()
        alb = AlbumCollector(q, lambda: 0.0, lambda m: 0)
        alb.tasks[("c", "g")] = asyncio.create_task(alb.flush(("c", "g")))
        await asyncio.sleep(0.05)
        assert q.empty()
    run(body())


# ───────────────────────────── QueueEngine ─────────────────────────────

def test_worker_delete_payload_unpacked():
    async def body():
        qe = QueueEngine(LoopGuard(FakeDB()),
                         AlbumCollector(asyncio.Queue(), lambda: 0, lambda m: 0),
                         AlbumCollector(asyncio.Queue(), lambda: 0, lambda m: 0))
        got = []

        async def del_handler(chat_key, ids):
            got.append((chat_key, ids))

        qe.tg_handlers["delete"] = del_handler
        task = asyncio.create_task(qe.workers()[0])
        await qe.q_tg.put(("delete", ("c1", [5, 6])))
        await asyncio.sleep(0.05)
        task.cancel()
        assert got == [("c1", [5, 6])]
    run(body())


def test_worker_paused_skips_and_exception_swallowed():
    async def body():
        qe = QueueEngine(LoopGuard(FakeDB()),
                         AlbumCollector(asyncio.Queue(), lambda: 0, lambda m: 0),
                         AlbumCollector(asyncio.Queue(), lambda: 0, lambda m: 0))
        calls = []

        async def new_handler(msgs):
            calls.append(msgs)

        qe.tg_handlers["new"] = new_handler
        qe.paused = True
        task = asyncio.create_task(qe.workers()[0])
        await qe.q_tg.put(("new", ["x"]))
        await asyncio.sleep(0.05)
        assert not calls                    # متوقف
        qe.paused = False

        async def boom(msgs):
            raise RuntimeError("x")
        qe.tg_handlers["new"] = boom        # در‌جا — کارگر به همان دیکشنر ارجاع دارد
        await qe.q_tg.put(("new", ["y"]))   # نباید کارگر را بکشد
        await asyncio.sleep(0.05)
        task.cancel()
        assert calls == []
    run(body())


def test_entry_points_filter_seen_and_route():
    async def body():
        db = FakeDB()
        qe = QueueEngine(LoopGuard(db),
                         AlbumCollector(asyncio.Queue(), lambda: 0.01, lambda m: m.id),
                         AlbumCollector(asyncio.Queue(), lambda: 0.01,
                                        lambda m: m["message_id"]))
        qe.albums_tg.queue = qe.q_tg
        qe.albums_bale.queue = qe.q_bale
        msg = SimpleNamespace(chat_id=-100, id=9, grouped_id=None)
        await qe.on_tg_new(msg)
        kind, payload = qe.q_tg.get_nowait()
        assert kind == "new" and payload == [msg]

        db.sent.add(("tg", "-100", 9))      # خودمان فرستاده‌ایم
        await qe.on_tg_new(msg)
        assert qe.q_tg.empty()

        await qe.on_tg_delete(-100, [9])    # بدون ignore → در صف
        kind, payload = qe.q_tg.get_nowait()
        assert kind == "delete" and payload == ("-100", [9])

        bm = {"message_id": 4, "chat": {"id": 5}, "media_group_id": "g"}
        await qe.queue_bale_msg(bm)         # آلبوم → بعد از تأخیر flush می‌شود
        await asyncio.sleep(0.05)
        kind, payload = qe.q_bale.get_nowait()
        assert kind == "new" and payload == [bm]
        await qe.queue_bale_edit(bm)
        assert qe.q_bale.get_nowait()[0] == "edit"
    run(body())


# ───────────────────────────── سازگاری نما ─────────────────────────────

def test_facade_paused_property_and_legacy_sets():
    br = Bridge(None, None, FakeDB(), SimpleNamespace(ALBUM_DELAY=0.01), 1, {"id": 2})
    assert br.paused is False
    br.paused = True
    assert br.queue.paused is True
    br._ignore_tg.add(("c", 1))
    assert ("c", 1) in br.guard.ignore_tg
    assert br.q_tg is br.queue.q_tg and br.q_bale is br.queue.q_bale


def test_facade_statics_and_delegation():
    assert Bridge._tg_kind(SimpleNamespace(
        media=None, action=None, photo=object(), video=None, video_note=None,
        voice=None, audio=None, gif=None, sticker=None, game=None, document=None,
        text=None, message=None)) == "photo"
    assert Bridge._bale_content({"text": "hi"})["kind"] == "text"
    from bridge.transfer import _fp
    assert fingerprint("k", "t") == _fp("k", "t")


def test_entities_build_utf16():
    # ایموجی = ۲ واحد UTF-16؛ حروف فارسی BMP = ۱ واحد
    ents = build_entities("🙂اب", [("bold", 0, 1, None), ("text_link", 1, 2, "http://x")])
    kinds = [type(e).__name__ for e in ents]
    assert kinds == ["MessageEntityBold", "MessageEntityTextUrl"]
    assert ents[0].offset == 0 and ents[1].offset == 2


def test_bale_content_photo_picks_largest():
    c = bale_content({"photo": [{"file_id": "a"}, {"file_id": "b"}], "caption": "کپ"})
    assert c["file_id"] == "b" and c["text"] == "کپ"

def test_tg_inbound_normalizes_marked_chat_id():
    """رویداد کانال با شناسهٔ -100… باید با کلید خالص صف/نگهبان شود (v2.17.6)."""
    async def body():
        db = FakeDB()
        db.sent.add(("tg", "3815616564", 9))    # خودمان قبلاً فرستاده‌ایم (خالص)
        qe = QueueEngine(LoopGuard(db),
                         AlbumCollector(asyncio.Queue(), lambda: 0.01, lambda m: m.id),
                         AlbumCollector(asyncio.Queue(), lambda: 0.01,
                                        lambda m: m["message_id"]))
        qe.albums_tg.queue = qe.q_tg
        qe.albums_bale.queue = qe.q_bale
        # پیام نشان‌دارِ «خودمان» → باید دیده شود و در صف نرود (ضدپژواک)
        await qe.on_tg_new(SimpleNamespace(chat_id=-1003815616564, id=9, grouped_id=None))
        assert qe.q_tg.empty()
        # پیام جدید نشان‌دار → در صف با کلید خالص
        msg = SimpleNamespace(chat_id=-1003815616564, id=10, grouped_id=None)
        await qe.on_tg_new(msg)
        kind, payload = qe.q_tg.get_nowait()
        assert kind == "new" and payload == [msg]
        # حذف نشان‌دار → کلید خالص
        await qe.on_tg_delete(-1003815616564, [11])
        kind, payload = qe.q_tg.get_nowait()
        assert kind == "delete" and payload == ("3815616564", [11])
    run(body())

# ───── فالبک ویرایش TG→Bale: suppress پژواک + ترتیب امن (رگرسیون v2.17.7) ─────

def _edit_msg(chat_id, mid=402, text="x"):
    return SimpleNamespace(chat_id=chat_id, id=mid, message=text, text=text,
                           entities=None, media=None, action=None, photo=None,
                           video=None, video_note=None, voice=None, audio=None,
                           gif=None, document=None, sticker=None, game=None,
                           file=None, poll=None, dice=None, contact=None,
                           geo=None, venue=None, grouped_id=None,
                           reply_to_msg_id=None, forward=None, via_bot=None)


def _edit_engine(bale, guard_calls, replace_ok=True):
    from bridge.transfer.sync_edit import EditSyncEngine

    db = SimpleNamespace(
        other_side=lambda p, c, m: [{"platform": "bale", "chat": "777",
                                     "msg": 55, "pair_id": 1, "row_id": 9}],
        get_pair=lambda pid: {"id": 1, "mode": "both", "bale_chat_id": 777},
        replace_map_dst=lambda *a: None,
        mark_sent=lambda *a: None,
    )
    t2b = SimpleNamespace(msg_to_bale=bale.resend)
    guard = SimpleNamespace(
        suppress=lambda p, c, m: guard_calls.append(("suppress", p, str(c), m)),
        release=lambda p, c, m: guard_calls.append(("release", p, str(c), m)),
    )
    cfg = SimpleNamespace(LIMIT_TEXT=4096)
    return EditSyncEngine(None, bale, db, cfg, t2b, None, guard)


def test_tg_edit_fallback_suppresses_echo_and_reorders():
    calls = []

    class Bale:
        def __init__(self):
            self.deleted = []

        async def edit_message_caption(self, chat, mid, body):
            from bridge.bot_api import BotAPIError
            raise BotAPIError("UpdateMessageDenied")

        async def edit_message_text(self, chat, mid, body):
            from bridge.bot_api import BotAPIError
            raise BotAPIError("UpdateMessageDenied")

        async def delete_message(self, chat, mid):
            self.deleted.append((chat, mid))
            return {"ok": True}

        async def resend(self, msg, dst, reply):
            calls.append(("resend", dst))
            return [66]

    bale = Bale()
    guard_calls = []
    eng = _edit_engine(bale, guard_calls)
    run(eng.process_tg_edit(_edit_msg(-1003815616564)))
    # پژواک حذفِ بله باید سرکوب شود (وگرنه نسخهٔ تلگرامی هم حذف می‌شد)
    assert ("suppress", "bale", "777", 55) in guard_calls
    assert not any(c[0] == "release" for c in guard_calls)
    # ترتیب امن: اول ارسال جایگزین، بعد حذف قدیمی
    assert calls and bale.deleted == [("777", 55)]


def test_tg_edit_fallback_send_fail_keeps_old_and_releases():
    from bridge.bot_api import BotAPIError

    class Bale:
        def __init__(self):
            self.deleted = []

        async def edit_message_caption(self, chat, mid, body):
            raise BotAPIError("UpdateMessageDenied")

        async def edit_message_text(self, chat, mid, body):
            raise BotAPIError("UpdateMessageDenied")

        async def delete_message(self, chat, mid):
            self.deleted.append((chat, mid))

        async def resend(self, msg, dst, reply):
            raise BotAPIError("send_document failed: InvalidArgument")

    bale = Bale()
    guard_calls = []
    eng = _edit_engine(bale, guard_calls)
    run(eng.process_tg_edit(_edit_msg(3815616564)))
    # ارسال جایگزین شکست خورد → قدیمی حذف نشد + suppress آزاد شد
    assert bale.deleted == []
    assert ("release", "bale", "777", 55) in guard_calls
