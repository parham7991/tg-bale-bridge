"""Fixtures مشترک تست‌ها — همه‌چیز آفلاین با Fake اجرا می‌شود."""
from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telethon import types as tg_t  # noqa: E402

from bridge.admin import Admin  # noqa: E402
from bridge.bale_api import BaleError  # noqa: E402
from bridge.db import DB  # noqa: E402
from bridge.transfer import Bridge  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class Cfg:
    """پیکربندی سبک برای تست (بدون نیاز به .env)."""

    def __init__(self, tmp: Path):
        self.TMP_DIR = tmp
        self.ALBUM_DELAY = 0.15
        self.MAX_BALE_UPLOAD = 50 * 1024 * 1024
        self.MAX_BALE_PHOTO = 10 * 1024 * 1024
        self.MAX_BALE_DOWNLOAD = 20 * 1024 * 1024
        self.LIMIT_TEXT = 4096
        self.LIMIT_CAPTION = 4096
        self.LIMIT_CAPTION_GROUP = 1024
        self.ADMIN_BALE_ID = 42


class FakeMsg:
    """جایگزین پیام Telethon."""

    def __init__(self, **kw):
        for k in ("media", "photo", "video", "video_note", "voice", "audio", "gif",
                  "sticker", "game", "document", "text", "message", "action",
                  "chat_id", "id", "grouped_id", "reply_to_msg_id", "forward",
                  "entities", "reply_to"):
            setattr(self, k, kw.get(k))

    async def download_media(self, file=None):
        p = Path(file) / f"dl_{self.id}.bin"
        p.write_bytes(b"0" * 128)
        return str(p)


class FakeSentMsg:
    def __init__(self, mid):
        self.id = mid
        self.chat_id = None


class FakeBale:
    """ضبط فراخوانی‌های BaleAPI."""

    def __init__(self):
        self.calls = []
        self._n = 1000
        self.fail_group = False

    def _ret(self, method, chat, **kw):
        self._n += 1
        self.calls.append((method, chat, kw))
        return {"message_id": self._n, "chat": {"id": chat}}

    async def send_message(self, chat, text, reply_to=None):
        return self._ret("sendMessage", chat, text=text, reply_to=reply_to)

    async def send_photo(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendPhoto", chat, caption=caption)

    async def send_document(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendDocument", chat, caption=caption)

    async def send_sticker(self, chat, path, reply_to=None):
        self.calls.append(("sendSticker", chat, {}))
        raise BaleError("sendSticker ناموفق")  # شبیه‌سازی متد پشتیبانی‌نشده

    async def send_voice(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendVoice", chat, caption=caption)

    async def send_video(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendVideo", chat, caption=caption)

    async def send_video_note(self, chat, path, reply_to=None):
        raise BaleError("sendVideoNote در بله نیست")

    async def send_animation(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendAnimation", chat, caption=caption)

    async def send_audio(self, chat, path, caption=None, reply_to=None):
        return self._ret("sendAudio", chat, caption=caption)

    async def send_location(self, chat, lat, lon, reply_to=None):
        return self._ret("sendLocation", chat, lat=lat, lon=lon)

    async def send_contact(self, chat, phone, first, last="", reply_to=None):
        return self._ret("sendContact", chat, phone=phone)

    async def send_media_group(self, chat, items, reply_to=None):
        if self.fail_group:
            raise BaleError("sendMediaGroup fail")
        out = []
        for item in items:
            out.append(self._ret("sendMediaGroup-item", chat, item=item[0]))
        return out

    async def edit_message_text(self, chat, mid, text):
        return self._ret("editMessageText", chat, mid=mid, text=text)

    async def edit_message_caption(self, chat, mid, caption):
        return self._ret("editMessageCaption", chat, mid=mid, caption=caption)

    async def delete_message(self, chat, mid):
        return self._ret("deleteMessage", chat, mid=mid)

    async def get_chat(self, chat_id):
        return {"id": 777, "username": "balech", "title": "کانال بله"}

    async def download_file(self, file_id, dest):
        Path(dest).write_bytes(b"1" * 64)
        return dest

    def methods(self):
        return [c[0] for c in self.calls]


class FakeTg:
    def __init__(self):
        self.calls = []
        self._n = 5000
        self.last_edit = None

    def _ret(self, method, **kw):
        self._n += 1
        self.calls.append((method, kw))
        return FakeSentMsg(self._n)

    async def send_message(self, entity, text, formatting_entities=None, reply_to=None):
        return self._ret("sendMessage", text=text, ents=formatting_entities, reply_to=reply_to)

    async def send_file(self, entity, file, caption=None, reply_to=None, **kw):
        return self._ret("sendFile", caption=caption, kw=kw, file=str(file)[:40])

    async def get_input_entity(self, chat_id):
        return chat_id

    async def get_entity(self, ref):
        if isinstance(ref, int) or (isinstance(ref, str) and ref.startswith("@tgch")):
            return tg_t.Channel(
                id=111, title="کانال تی‌جی", photo=tg_t.ChatPhotoEmpty(),
                date=datetime.datetime.now(), broadcast=True,
                megagroup=False, username="tgch",
            )
        raise ValueError("not found")

    async def get_messages(self, entity, ids):
        outer = self

        class M:
            async def edit(self, text, formatting_entities=None):
                outer.last_edit = text
                return True

        return M()

    async def delete_messages(self, entity, ids):
        self.calls.append(("deleteMessages", {"ids": ids}))


@pytest.fixture
def cfg(tmp_path):
    return Cfg(tmp_path)


@pytest.fixture
def db(tmp_path):
    return DB(tmp_path / "test.db")


@pytest.fixture
def bale():
    return FakeBale()


@pytest.fixture
def tg():
    return FakeTg()


@pytest.fixture
def bridge(tg, bale, db, cfg):
    return Bridge(tg, bale, db, cfg, 999, {"id": 42, "username": "mirbot"})


@pytest.fixture
def admin(db, bale, tg, bridge):
    return Admin(db, bale, tg, bridge, _admin_cfg())


def _admin_cfg():
    class A:
        ADMIN_BALE_ID = 42
    return A()


@pytest.fixture
def pair(db):
    return db.add_pair(-100111, "کانال تی‌جی", "tgch", "777", "کانال بله", "balech", "both")
