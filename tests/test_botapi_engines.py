"""تست‌های بستهٔ کلاینت Bot-API (bridge/botapi) — آفلاین با نشست/واکنش جعلی."""
from __future__ import annotations

import asyncio

import pytest

import bridge.botapi.transport as transport_mod
from bridge.botapi import BotAPI, BotAPIError
from bridge.botapi.events import ListenEngine
from bridge.botapi.files import FilesEngine
from bridge.botapi.session import BotAPISession
from bridge.botapi.types_map import (
    MEDIA_METHODS,
    build_file_url,
    build_media_group,
    build_url,
    normalize_base,
)
from tests.conftest import run

# ───────────────────────────── فیک‌ها ─────────────────────────────

class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    async def json(self, content_type=None):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


class _PostCM:
    """async context manager مثل aiohttp ClientResponse."""

    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, *a):
        return False


class FakeSession:
    """نشست جعلی — پاسخ‌های نوبتی از صف."""

    def __init__(self, responses=None, fail_times=0):
        self.responses = list(responses or [])
        self.fail_times = fail_times
        self.posts = []          # (url, json یا form)
        self.failed = 0
        self.closed = False

    def post(self, url, json=None, data=None):
        self.posts.append((url, json if json is not None else data))
        if self.failed < self.fail_times:
            self.failed += 1
            raise asyncio.TimeoutError("boom")
        return _PostCM(FakeResp(self.responses.pop(0) if self.responses
                                else {"ok": True}))

    async def close(self):
        self.closed = True


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []

    _real = asyncio.sleep

    async def fake_sleep(sec):
        sleeps.append(sec)
        await _real(0)           # همکاری — حلقه‌ها فرصت اجرا داشته باشند

    monkeypatch.setattr(transport_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr("bridge.botapi.events.asyncio.sleep", fake_sleep)
    return sleeps


# ───────────────────────────── types_map ─────────────────────────────

def test_url_builders_and_base():
    assert normalize_base("https://x.example.com/") == "https://x.example.com"
    assert normalize_base("") == "https://tapi.bale.ai"
    assert build_url("https://tapi.bale.ai", "123:abc", "getMe") == \
        "https://tapi.bale.ai/bot123:abc/getMe"
    assert build_file_url("https://tapi.bale.ai", "T", "a/b") == \
        "https://tapi.bale.ai/file/botT/a/b"


def test_media_methods_table():
    assert MEDIA_METHODS["photo"] == ("sendPhoto", "photo")
    assert MEDIA_METHODS["video_note"] == ("sendVideoNote", "video_note")
    assert len(MEDIA_METHODS) == 8


def test_build_media_group_payload():
    files, media = build_media_group([("photo", "/a.jpg", "کپ"),
                                      ("video", "/b.mp4", "")])
    assert files == {"f0": "/a.jpg", "f1": "/b.mp4"}
    assert media[0] == {"type": "photo", "media": "attach://f0", "caption": "کپ"}
    assert media[1]["caption"] is None            # کپشن خالی → None
    long_cap = build_media_group([("photo", "/x", "ط" * 2000)])[1][0]["caption"]
    assert len(long_cap) == 1024                  # سقف کپشن آلبوم


# ───────────────────────────── خطا و نشست ─────────────────────────────

def test_error_attributes():
    e = BotAPIError("شرح", 400, {"retry_after": 3})
    assert e.description == "شرح" and e.error_code == 400
    assert e.parameters == {"retry_after": 3}


def test_session_rebuild_after_close(monkeypatch):
    made = []

    class FakeCS:
        def __init__(self, timeout=None):
            self.closed = False
            made.append(self)

        async def close(self):
            self.closed = True

    monkeypatch.setattr("bridge.botapi.session.aiohttp.ClientSession", FakeCS)
    s = BotAPISession()
    a = run(s.get())
    b = run(s.get())
    assert a is b and len(made) == 1          # تنبل و یکتا
    run(s.close())
    c = run(s.get())
    assert c is not a and len(made) == 2      # پس از بستن دوباره ساخته می‌شود


# ───────────────────────────── transport ─────────────────────────────

def test_call_ok_filters_none_params():
    fs = FakeSession([{"ok": True, "result": {"message_id": 5}}])
    api = BotAPI("t")
    api.session_engine.session = fs
    out = run(api.call("sendMessage", {"chat_id": 1, "text": "s", "reply_to": None}))
    assert out == {"message_id": 5}
    sent_json = fs.posts[0][1]
    assert "reply_to" not in sent_json and sent_json["text"] == "s"


def test_call_api_error_raises_without_retry():
    fs = FakeSession([{"ok": False, "description": "chat not found", "error_code": 400}])
    api = BotAPI("t")
    api.session_engine.session = fs
    with pytest.raises(BotAPIError) as ei:
        run(api.call("getChat", {"chat_id": 9}))
    assert ei.value.error_code == 400 and "chat not found" in ei.value.description
    assert len(fs.posts) == 1                 # بدون retry_after → یک تلاش


def test_call_rate_limit_retries_then_succeeds(no_sleep):
    fs = FakeSession([
        {"ok": False, "description": "too fast", "error_code": 429,
         "parameters": {"retry_after": 2}},
        {"ok": True, "result": 7},
    ])
    api = BotAPI("t")
    api.session_engine.session = fs
    assert run(api.call("sendMessage", {"chat_id": 1, "text": "x"})) == 7
    assert len(fs.posts) == 2 and no_sleep == [2.5]


def test_call_network_failure_retries_then_raises(no_sleep):
    fs = FakeSession(fail_times=3)
    api = BotAPI("t")
    api.session_engine.session = fs
    with pytest.raises(BotAPIError) as ei:
        run(api.call("getMe"))
    assert "خطای شبکه" in ei.value.description
    assert fs.failed == 3 and no_sleep == [1.5, 3.0]   # دوبار retry


def test_call_multipart_uses_formdata(tmp_path):
    import aiohttp

    f = tmp_path / "a.jpg"
    f.write_bytes(b"img")
    fs = FakeSession([{"ok": True, "result": 1}])
    api = BotAPI("t")
    api.session_engine.session = fs
    run(api.send_media_group(1, [("photo", str(f), "کپ")]))
    assert "sendMediaGroup" in fs.posts[0][0]
    assert isinstance(fs.posts[0][1], aiohttp.FormData)


# ───────────────────────────── facade (پچ call) ─────────────────────────────

def test_facade_methods_route_params():
    api = BotAPI("t")
    seen = []

    async def fake_call(method, params=None, files=None):
        seen.append((method, params, files))
        return {"message_id": 1}

    api.call = fake_call
    run(api.send_message(1, "سلام", reply_to=5, reply_markup={"kb": 1}))
    assert seen[-1] == ("sendMessage",
                        {"chat_id": 1, "text": "سلام", "reply_to_message_id": 5,
                         "reply_markup": {"kb": 1}}, None)
    run(api.send_message(1, "بدون مارک‌آپ"))
    assert "reply_markup" not in seen[-1][1]
    run(api.send_photo(1, "/p.jpg", caption="ک", reply_to=2))
    assert seen[-1] == ("sendPhoto",
                        {"chat_id": 1, "caption": "ک", "reply_to_message_id": 2},
                        {"photo": "/p.jpg"})
    run(api.send_sticker(1, "/s.webp", reply_to=None))
    assert seen[-1][2] == {"sticker": "/s.webp"}
    run(api.send_media_group(1, [("photo", "/a", None), ("video", "/b", "ک")], reply_to=3))
    assert seen[-1][0] == "sendMediaGroup" and set(seen[-1][2]) == {"f0", "f1"}


def test_facade_chat_action_swallows_error():
    api = BotAPI("t")

    async def boom(method, params=None, files=None):
        raise BotAPIError("x")

    api.call = boom
    assert run(api.send_chat_action(1)) is None


# ───────────────────────────── listen ─────────────────────────────

def test_listen_bootstrap_and_dispatch():
    api = BotAPI("t")
    batches = [[{"update_id": 10}], [{"update_id": 11}, {"update_id": 12}], []]
    got = []

    async def fake_updates(offset=None, timeout=30):
        await asyncio.sleep(0)                    # yield — تا cancel بنشیند
        return batches.pop(0) if batches else []

    api.get_updates = fake_updates
    le = ListenEngine(api)

    async def handler(upd, offset):
        got.append((upd["update_id"], offset))
        if upd["update_id"] == 12:
            raise RuntimeError("handler boom")   # نباید حلقه را بکشد
        if upd["update_id"] == 12:
            raise KeyboardInterrupt
    async def body():
        t = asyncio.create_task(le.listen(handler, offset=None, timeout=0))
        await asyncio.sleep(0.15)
        t.cancel()
    run(body())
    assert [g[0] for g in got] == [11, 12]    # ۱۰ در bootstrap مصرف شد (باطله)
    assert got[0][1] == 12                    # آفست قبل از هندلر جلو می‌رود
    assert got[1][1] == 13                    # آفست جلو می‌رود


def test_listen_survives_api_errors(monkeypatch):
    monkeypatch.setattr("bridge.botapi.events.ERROR_SLEEP", 0)   # خواب صفر در تست
    api = BotAPI("t")
    calls = {"n": 0}

    async def fake_updates(offset=None, timeout=30):
        await asyncio.sleep(0)                    # yield — مسیر تاخیر ۵ ثانیه‌ای
        calls["n"] += 1
        if calls["n"] <= 2:
            raise BotAPIError("سرور") if calls["n"] == 1 else TimeoutError("نت")
        raise KeyboardInterrupt              # خروج از حلقه

    api.get_updates = fake_updates
    with pytest.raises(KeyboardInterrupt):
        run(ListenEngine(api).listen(lambda u, o: None, offset=5, timeout=0))
    assert calls["n"] == 3


# ───────────────────────────── files ─────────────────────────────

def test_download_file_streams_to_dest(tmp_path):
    class FakeContent:
        async def iter_chunked(self, n):
            yield b"hello "
            yield b"world"

    class FakeGetResp:
        status = 200

        def raise_for_status(self):
            pass

        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeFS:
        def get(self, url):
            assert "/file/botT/p" in url
            return FakeGetResp()              # خودش async CM است

    api = BotAPI("T")
    api.get_file = lambda file_id: _coro({"file_path": "p"})
    api._get_session = lambda: _coro(FakeFS())
    dest = tmp_path / "out.bin"
    out = run(FilesEngine(api).download_file("fid", dest))
    assert out == dest and dest.read_bytes() == b"hello world"


def test_download_file_without_path_raises(tmp_path):
    api = BotAPI("T")
    api.get_file = lambda file_id: _coro({})
    with pytest.raises(BotAPIError):
        run(FilesEngine(api).download_file("fid", tmp_path / "x"))


async def _coro(value):
    return value
