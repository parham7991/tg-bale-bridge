"""تست‌های سلف‌بات بله (aiobale): آداپتور BaleUserAPI + همگام‌سازی حذف بله→تلگرام."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from aiobale.enums import ChatType, PeerType
from aiobale.types import Chat, Message, MessageContent, Peer, SelectedMessages
from aiobale.types.message_content import DocumentMessage, MessageCaption, TextMessage

from bridge.bale import BaleUserAPI, _classify_document
from bridge.db import DB
from bridge.transfer import Bridge
from tests.conftest import Cfg, run


def make_text_msg(text="سلام دنیا", chat_id=123, mid=5, chat_type=ChatType.CHANNEL):
    return Message(
        chat=Chat(type=chat_type, id=chat_id),
        sender_id=42,
        date=1700000000,
        message_id=mid,
        content=MessageContent(text=TextMessage(value=text)),
    )


def make_doc_msg(mime="image/jpeg", name="a.jpg", caption=None, chat_id=123, mid=6):
    doc = DocumentMessage(
        file_id=555,
        access_hash=999,
        size=1234,
        name=name,
        mime_type=mime,
        caption=MessageCaption(content=caption) if caption else None,
    )
    return Message(
        chat=Chat(type=ChatType.CHANNEL, id=chat_id),
        sender_id=42,
        date=1700000001,
        message_id=mid,
        content=MessageContent(document=doc),
    )


class FakeAioClient:
    """جایگزین aiobale.Client — همه‌چیز آفلاین."""

    def __init__(self):
        self.calls = []
        self.me = SimpleNamespace(id=900, name="من", username="@me_user")
        self.seq = 0

    async def start(self, run_in_background=False, signal_handling=True, phone_number=None):
        self.calls.append(("start", run_in_background, signal_handling))

    async def stop(self):
        self.calls.append(("stop",))

    async def get_me(self):
        return self.me

    async def load_user(self, uid, chat_type=None):
        return SimpleNamespace(id=uid, name="من", username="me_user")

    async def get_full_group(self, cid):
        raise RuntimeError("not a group")

    async def search_username(self, username):
        return SimpleNamespace(user=SimpleNamespace(id=654, name="کانال", username=username))

    def _sent(self, name, args):
        self.seq += 1
        self.calls.append((name,) + args)
        return SimpleNamespace(message_id=100 + self.seq, date=1700000100 + self.seq)

    async def send_message(self, text=None, chat_id=None, chat_type=None, reply_to=None, **kw):
        return self._sent("send_message", (text, chat_id, chat_type, reply_to))

    async def send_photo(self, photo=None, chat_id=None, chat_type=None, caption=None,
                         reply_to=None, **kw):
        return self._sent("send_photo", (photo, chat_id, chat_type, caption, reply_to))

    async def send_video(self, video=None, chat_id=None, chat_type=None, caption=None,
                         reply_to=None, **kw):
        return self._sent("send_video", (video, chat_id, chat_type, caption))

    async def send_document(self, file=None, chat_id=None, chat_type=None, caption=None,
                            reply_to=None, **kw):
        return self._sent("send_document", (file, chat_id, chat_type, caption))

    async def send_gif(self, gif=None, chat_id=None, chat_type=None, caption=None,
                       reply_to=None, **kw):
        return self._sent("send_gif", (gif, chat_id, chat_type, caption))

    async def edit_message(self, text=None, message_id=None, chat_id=None, chat_type=None, **kw):
        self.calls.append(("edit_message", text, message_id, chat_id, chat_type))
        return SimpleNamespace(ok=True)

    async def delete_message(self, message_id=None, message_date=None, chat_id=None,
                             chat_type=None, **kw):
        self.calls.append(("delete_message", message_id, message_date, chat_id, chat_type))
        return SimpleNamespace(ok=True)

    async def download_file(self, file_id=None, access_hash=None, destination=None, seek=True):
        self.calls.append(("download_file", file_id, access_hash, destination))
        Path(destination).write_bytes(b"x")
        return destination


def make_api(tmp_path, fake=None):
    fake = fake or FakeAioClient()
    api = BaleUserAPI(db=DB(tmp_path / "d.db"), client=fake)
    return api, fake


# ───────────────────────────── normalize ─────────────────────────────

def test_normalize_text(tmp_path):
    api, _ = make_api(tmp_path)
    out = api.normalize(make_text_msg("سلام دنیا"))
    assert out["text"] == "سلام دنیا"
    assert out["message_id"] == 5
    assert out["date"] == 1700000000
    assert out["chat"]["id"] == 123
    assert out["chat"]["type"] == "channel"
    assert out["from"]["id"] == 42


def test_normalize_photo_with_caption(tmp_path):
    api, _ = make_api(tmp_path)
    out = api.normalize(make_doc_msg("image/jpeg", "pic.jpg", caption="کپشن"))
    assert out["photo"][0]["file_id"] == "555"
    assert out["photo"][0]["file_size"] == 1234
    assert out["caption"] == "کپشن"
    assert "document" not in out
    # access_hash برای دانلود بعدی کش می‌شود
    assert api._files["555"] == 999


def test_normalize_voice_and_document(tmp_path):
    api, _ = make_api(tmp_path)
    out = api.normalize(make_doc_msg("audio/ogg", "voice.ogg"))
    assert "voice" in out and out["voice"]["mime_type"] == "audio/ogg"
    out2 = api.normalize(make_doc_msg("application/pdf", "doc.pdf"))
    assert "document" in out2 and out2["document"]["file_name"] == "doc.pdf"


def test_classify_document():
    ns = lambda m, n: SimpleNamespace(mime_type=m, name=n, ext=None)  # noqa: E731
    assert _classify_document(ns("image/png", "a.png")) == "photo"
    assert _classify_document(ns("image/gif", "a.gif")) == "animation"
    assert _classify_document(ns("video/mp4", "a.mp4")) == "video"
    assert _classify_document(ns("audio/mpeg", "a.mp3")) == "audio"
    assert _classify_document(ns("audio/ogg", "v.ogg")) == "voice"
    assert _classify_document(ns("application/pdf", "a.pdf")) == "document"


# ───────────────────────────── رویداد حذف ─────────────────────────────

def test_deleted_event_update(tmp_path):
    api, _ = make_api(tmp_path)
    got = []

    async def handler(upd, offset):
        got.append(upd)

    api._handler = handler
    # SelectedMessages فقط فرمت سیمی protobuf (aliasهای "1"/"2"/"3") را decode می‌کند؛
    # "0506" یعنی varint-packed ‏[5, 6] و "0102" یعنی ‏[1, 2].
    sel = SelectedMessages(
        **{"1": Peer(type=PeerType.GROUP, id=123), "2": "0506", "3": {"1": "0102"}}
    )
    run(api._on_deleted(sel))
    dm = got[0]["deleted_messages"]
    assert dm["chat"]["id"] == 123
    assert dm["message_ids"] == [5, 6]


# ───────────────────────────── ارسال ─────────────────────────────

def test_send_message_reply_and_chat_type(tmp_path):
    api, fake = make_api(tmp_path)
    api._chat_types["123"] = "channel"
    res = run(api.send_message(123, "متن", reply_to=7))
    name, text, chat_id, chat_type, reply = fake.calls[-1]
    assert name == "send_message" and text == "متن"
    assert chat_id == 123 and chat_type == ChatType.CHANNEL
    assert reply is not None and reply.message_id == 7
    assert res["message_id"] == 101


def test_send_sticker_falls_back_to_document(tmp_path):
    api, fake = make_api(tmp_path)
    api._chat_types["1"] = "private"
    run(api.send_sticker(1, "x.webp"))
    assert fake.calls[-1][0] == "send_document"


def test_send_location_degrades_to_text(tmp_path):
    api, fake = make_api(tmp_path)
    api._chat_types["1"] = "private"
    run(api.send_location(1, 35.7, 51.4))
    name, text, *_ = fake.calls[-1]
    assert name == "send_message" and "35.7" in text


def test_delete_message_uses_cached_date(tmp_path):
    api, fake = make_api(tmp_path)
    api._chat_types["123"] = "channel"
    api.normalize(make_text_msg())  # کش (123, 5) → 1700000000
    run(api.delete_message(123, 5))
    name, mid, date, chat_id, ct = fake.calls[-1]
    assert name == "delete_message"
    assert mid == 5 and date == 1700000000
    assert chat_id == 123


def test_get_me_normalized(tmp_path):
    api, fake = make_api(tmp_path)
    me = run(api.get_me())
    assert me["id"] == 900
    assert me["is_bot"] is False
    assert me["username"] == "me_user"
    assert fake.calls[0][0] == "start"


# ───────────────────────────── حذف بله→تلگرام ─────────────────────────────

class FakeTgDel:
    def __init__(self):
        self.deleted = []

    async def delete_messages(self, chat_id, ids):
        self.deleted.append((chat_id, list(ids)))


def _bridge_with_map(tmp_path):
    db = DB(tmp_path / "d.db")
    pair_id = db.add_pair(-1001, "tg", "", "123", "bale", "", "both")
    db.add_map(pair_id, "bale", "123", 5, "tg", "-1001", 7)
    api, fake = make_api(tmp_path, FakeAioClient())
    api.has_delete_events = True
    tg = FakeTgDel()
    br = Bridge(tg, api, db, Cfg(tmp_path), 1, {"id": 900})
    return br, db, tg


def test_process_bale_delete_mirrors_to_tg(tmp_path):
    br, db, tg = _bridge_with_map(tmp_path)
    run(br._process_bale_delete("123", [5]))
    assert tg.deleted == [(-1001, [7])]
    assert not db.other_side("bale", "123", 5)
    assert ("‑1001".replace("\u2011", "-"), 7) in br._ignore_tg or ("-1001", 7) in br._ignore_tg


def test_process_bale_delete_respects_mode(tmp_path):
    br, db, tg = _bridge_with_map(tmp_path)
    pid = db.list_pairs()[0]["id"]
    db.set_mode(pid, "tg2bale")
    run(br._process_bale_delete("123", [5]))
    assert tg.deleted == []


def test_on_bale_delete_queues_and_filters_echo(tmp_path):
    br, db, tg = _bridge_with_map(tmp_path)
    run(br.on_bale_delete(123, [5]))
    kind, payload = br.q_bale.get_nowait()
    assert kind == "delete" and payload == ("123", [5])

    br._ignore_bale.add(("123", 5))
    run(br.on_bale_delete(123, [5, 6]))
    kind, payload = br.q_bale.get_nowait()
    assert payload == ("123", [6])


# ─────────────── رگرسیون v2.17.2: resolve کانال از search_username ───────────────

def test_extract_id_reads_group_field():
    """پاسخ search_username برای «گروه/کانال» در فیلد group است نه user."""
    from types import SimpleNamespace as NS

    from bridge.bale.types_map import extract_id

    # شکل aiobale: ContactResponse(group=Peer(id=...))
    resp = NS(user=None, group=NS(id=-1001234567890, username="marvellit"))
    assert extract_id(resp) == -1001234567890
    # شکل dict
    assert extract_id({"group": {"id": 42, "username": "x"}}) == 42
    # کاربر (فیلد user) مثل قبل
    assert extract_id(NS(user=NS(id=77), group=None)) == 77
    # مستقیم روی خود Peer
    assert extract_id(NS(id=5)) == 5
