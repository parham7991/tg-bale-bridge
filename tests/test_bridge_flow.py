"""جریان‌های سرتاسری موتور همگام‌سازی (تلگرام ⇄ بله) با Fake."""
from __future__ import annotations

import asyncio

from tests.conftest import FakeMsg, run


async def _with_workers(bridge, body):
    workers = [asyncio.create_task(w) for w in bridge.workers()]
    try:
        await asyncio.sleep(0)
        await body()
    finally:
        for w in workers:
            w.cancel()


class TestTgToBale:
    def test_text_mirror_creates_map(self, bridge, db, bale, pair):
        async def body():
            await bridge.on_tg_new(FakeMsg(text="سلام دنیا", message="سلام دنیا",
                                           chat_id=-100111, id=11))
            await asyncio.sleep(0.25)
        run(_with_workers(bridge, body))
        assert any(c[0] == "sendMessage" and "سلام" in str(c[2].get("text", ""))
                   for c in bale.calls)
        o = db.other_side("tg", "-100111", 11, pair)
        assert o and o[0]["platform"] == "bale"

    def test_loop_guard(self, bridge, db, bale, tg, pair):
        async def body():
            db.mark_sent("bale", "777", 555)
            await bridge.queue_bale_msg({"message_id": 555,
                                         "chat": {"id": 777, "type": "channel"}, "text": "x"})
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        assert not any(c[0] == "sendMessage" and c[1].get("text") == "x" for c in tg.calls)

    def test_sticker_falls_back_to_document(self, bridge, bale, pair):
        async def body():
            await bridge.on_tg_new(FakeMsg(sticker=object(), document=object(),
                                           message="", chat_id=-100111, id=12))
            await asyncio.sleep(0.25)
        run(_with_workers(bridge, body))
        assert "sendSticker" in bale.methods() and "sendDocument" in bale.methods()
        caps = [c[2].get("caption") for c in bale.calls if c[0] == "sendDocument"]
        assert any("استیکر" in (cap or "") for cap in caps)

    def test_video_note_falls_back_to_video(self, bridge, bale, pair):
        async def body():
            await bridge.on_tg_new(FakeMsg(video_note=object(), message="",
                                           chat_id=-100111, id=13))
            await asyncio.sleep(0.25)
        run(_with_workers(bridge, body))
        assert "sendVideo" in bale.methods()

    def test_album(self, bridge, db, bale, pair, cfg):
        async def body():
            for i in range(3):
                await bridge.on_tg_new(FakeMsg(photo=object(), message="کپشن" if i == 0 else "",
                                               chat_id=-100111, id=20 + i, grouped_id=9))
            await asyncio.sleep(cfg.ALBUM_DELAY + 0.4)
        run(_with_workers(bridge, body))
        assert "sendMediaGroup-item" in bale.methods()
        assert db.other_side("tg", "-100111", 20, pair)
        assert db.other_side("tg", "-100111", 22, pair)

    def test_album_fallback_sequential(self, bridge, db, bale, pair, cfg):
        async def body():
            bale.fail_group = True
            for i in range(2):
                await bridge.on_tg_new(FakeMsg(photo=object(), message="",
                                               chat_id=-100111, id=30 + i, grouped_id=10))
            await asyncio.sleep(cfg.ALBUM_DELAY + 0.5)
        run(_with_workers(bridge, body))
        assert db.other_side("tg", "-100111", 30, pair)
        assert db.other_side("tg", "-100111", 31, pair)

    def test_edit_sync(self, bridge, bale, pair):
        async def body():
            await bridge.on_tg_new(FakeMsg(text="اولیه", message="اولیه",
                                           chat_id=-100111, id=11))
            await asyncio.sleep(0.2)
            await bridge.on_tg_edit(FakeMsg(text="ویرایش‌شده", message="ویرایش‌شده",
                                            chat_id=-100111, id=11))
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        assert any(c[0] == "editMessageText" and "ویرایش‌شده" in str(c[2].get("text", ""))
                   for c in bale.calls)

    def test_delete_sync(self, bridge, db, bale, pair):
        async def body():
            await bridge.on_tg_new(FakeMsg(text="x", message="x", chat_id=-100111, id=11))
            await asyncio.sleep(0.2)
            await bridge.on_tg_delete(-100111, [11])
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        assert "deleteMessage" in bale.methods()
        assert not db.other_side("tg", "-100111", 11, pair)

    def test_poll_render(self, bridge, bale, pair):
        from telethon import types as tg_t

        poll = tg_t.MessageMediaPoll(
            poll=tg_t.Poll(
                id=1, question=tg_t.TextWithEntities(text="غذا؟", entities=[]),
                answers=[tg_t.PollAnswer(text=tg_t.TextWithEntities(text="پیتزا", entities=[]),
                                         option=b"0")],
                closed=False, multiple_choice=False, quiz=False, public_voters=True, hash=0,
            ),
            results=None,
        )
        async def body():
            await bridge.on_tg_new(FakeMsg(media=poll, message="", chat_id=-100111, id=40))
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        assert any(c[0] == "sendMessage" and "نظرسنجی" in str(c[2].get("text", ""))
                   for c in bale.calls)


class TestBaleToTg:
    def test_text_with_entities(self, bridge, db, tg, pair):
        async def body():
            await bridge.queue_bale_msg({"message_id": 80,
                                         "chat": {"id": 777, "type": "channel"},
                                         "text": "*مهم* خبر [سایت](https://s.ir)"})
            await asyncio.sleep(0.25)
        run(_with_workers(bridge, body))
        sm = [c for c in tg.calls if c[0] == "sendMessage"]
        assert sm and "مهم" in sm[-1][1]["text"]
        kinds = {type(e).__name__ for e in sm[-1][1]["ents"] or []}
        assert "MessageEntityBold" in kinds and "MessageEntityTextUrl" in kinds
        assert db.other_side("bale", "777", 80, pair)

    def test_photo_with_forward_header(self, bridge, tg, pair):
        async def body():
            await bridge.queue_bale_msg({
                "message_id": 81, "chat": {"id": 777, "type": "channel"},
                "photo": [{"file_id": "p1", "file_size": 10},
                          {"file_id": "p2", "file_size": 20}],
                "caption": "کپشن عکس",
                "forward_from_chat": {"id": 5, "title": "منبع", "username": "src"},
            })
            await asyncio.sleep(0.25)
        run(_with_workers(bridge, body))
        sf = [c for c in tg.calls if c[0] == "sendFile"]
        assert sf and "باز‌ارسال از: منبع" in (sf[-1][1]["caption"] or "")

    def test_edit_sync(self, bridge, db, tg, pair):
        async def body():
            await bridge.queue_bale_msg({"message_id": 80,
                                         "chat": {"id": 777, "type": "channel"},
                                         "text": "نسخه اول"})
            await asyncio.sleep(0.2)
            await bridge.queue_bale_edit({"message_id": 80,
                                          "chat": {"id": 777, "type": "channel"},
                                          "text": "نسخه دوم"})
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        assert tg.last_edit == "نسخه دوم"

    def test_oversized_file_gets_notice(self, bridge, tg, pair, cfg):
        async def body():
            cfg.MAX_BALE_DOWNLOAD = 1  # همه‌چیز «حجیم» است
            await bridge.queue_bale_msg({
                "message_id": 90, "chat": {"id": 777, "type": "channel"},
                "document": {"file_id": "d1", "file_name": "big.zip", "file_size": 999},
            })
            await asyncio.sleep(0.2)
        run(_with_workers(bridge, body))
        sm = [c for c in tg.calls if c[0] == "sendMessage"]
        assert sm and "بزرگ‌تر از سقف" in sm[-1][1]["text"]
