"""تست‌های بستهٔ سلف تلگرام (bridge/tguser) — آفلاین با فیک‌های کامل."""
from __future__ import annotations

from types import SimpleNamespace

from telethon.errors import SessionPasswordNeededError

from bridge.tguser import TgSelfBot, register
from bridge.tguser.gateway import TgSelfGateway
from bridge.tguser.login import TgLoginEngine
from bridge.tguser.routing import TgEventRouter
from bridge.tguser.session import TgSelfSession
from bridge.tguser.types_map import (
    bare_chat_id,
    has_forward,
    is_saved_messages,
    text_of,
)
from tests.conftest import run

# ───────────────────────────── فیک‌ها ─────────────────────────────

class FakeSelfTgClient:
    """کلاینت جعلی سلف — هم برای ثبت هندلر هم برای لاگین/پروب."""

    def __init__(self, me=None, authorized=False, fail_get_messages=False):
        self.me = me or SimpleNamespace(username="selfuser", first_name="پرهام")
        self.authorized = authorized
        self.fail_get_messages = fail_get_messages
        self.handlers = []          # (event_class, handler)
        self.sent = []              # (chat_id, text, kwargs)
        self.calls = []             # نام متدها به ترتیب
        self.disconnects = 0
        self.code_hash = "HASH1"

    def on(self, event_cls):
        def deco(fn):
            self.handlers.append((type(event_cls).__name__, fn))
            return fn
        return deco

    async def connect(self):
        self.calls.append("connect")

    async def is_user_authorized(self):
        self.calls.append("auth")
        return self.authorized

    async def send_code_request(self, phone):
        self.calls.append("code")
        return SimpleNamespace(phone_code_hash=self.code_hash)

    async def sign_in(self, phone=None, code=None, phone_code_hash=None,
                      password=None):
        self.calls.append(f"signin:{code or password}")
        if code == "bad":
            raise ValueError("-phone-code-invalid")
        if code == "2fa" or password == "needpw":
            raise SessionPasswordNeededError(request=None)
        if password == "wrongpw":
            raise ValueError("password hash invalid")

    async def get_me(self):
        self.calls.append("me")
        return self.me

    async def disconnect(self):
        self.disconnects += 1

    async def get_messages(self, chat_id, limit=None, ids=None):
        if self.fail_get_messages and limit is not None:
            raise TypeError("proxy takes no limit")  # فقط مسیر limit — مثل امضای قدیمی
        self.calls.append(f"gm:{chat_id}")
        return [SimpleNamespace(id=1)]

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))
        return SimpleNamespace(id=len(self.sent) + 1)


class FakeBridge:
    def __init__(self):
        self.new, self.edit, self.delete = [], [], []

    async def on_tg_new(self, msg):
        self.new.append(msg)

    async def on_tg_edit(self, msg):
        self.edit.append(msg)

    async def on_tg_delete(self, chat_id, ids):
        self.delete.append((chat_id, ids))


class FakeAdmin:
    def __init__(self, reply="پاسخ پنل"):
        self.reply = reply
        self.calls = []

    async def handle(self, platform, chat_id, uid, text, msg):
        self.calls.append((platform, chat_id, uid, text))
        return self.reply


def tg_msg(chat_id, text=None, forward=None):
    return SimpleNamespace(chat_id=chat_id, message=text, forward=forward)


def event(msg=None, client=None, chat_id=None, deleted_ids=None):
    return SimpleNamespace(message=msg, client=client, chat_id=chat_id,
                           deleted_ids=deleted_ids)


# ───────────────────────────── types_map ─────────────────────────────

def test_saved_messages_and_text_and_forward():
    assert is_saved_messages(tg_msg(123, "x"), 123)
    assert not is_saved_messages(tg_msg(-100, "x"), 123)
    assert text_of(tg_msg(1, "  سلام ")) == "سلام"
    assert text_of(tg_msg(1, None)) == ""
    assert has_forward(tg_msg(1, None, forward=object()))
    assert not has_forward(tg_msg(1, "فقط متن"))


# ───────────────────────────── نشست ─────────────────────────────

def test_session_build_uses_str_path(monkeypatch):
    made = {}

    class FakeTC:
        def __init__(self, path, aid, ahash):
            made["args"] = (path, aid, ahash)

    monkeypatch.setattr("telethon.TelegramClient", FakeTC)
    TgSelfSession.build("/tmp/x", 12, "ab")
    assert made["args"] == ("/tmp/x", 12, "ab")


def test_session_connect_authorized_handles_failure():
    class Boom:
        async def connect(self):
            raise ConnectionError("down")

    assert run(TgSelfSession.connect_authorized(Boom())) is False
    ok_client = FakeSelfTgClient(authorized=True)
    assert run(TgSelfSession.connect_authorized(ok_client)) is True


# ───────────────────────────── دروازه ─────────────────────────────

def test_resolve_credentials_cascade():
    cfg = SimpleNamespace(TG_API_ID=11, TG_API_HASH="cfg")
    store = SimpleNamespace(tg_api=lambda: {"api_id": 22, "api_hash": "db"})
    # data > cfg > store
    assert TgSelfGateway.resolve_credentials(cfg, store, 33, "data") == (33, "data")
    assert TgSelfGateway.resolve_credentials(cfg, store) == (11, "cfg")
    assert TgSelfGateway.resolve_credentials(
        SimpleNamespace(TG_API_ID=0, TG_API_HASH=""), store) == (22, "db")


def test_ready_client_none_without_store_or_creds():
    assert run(TgSelfGateway.ready_client(
        SimpleNamespace(TG_API_ID=0, TG_API_HASH=""),
        SimpleNamespace(has_tg=lambda c: False))) is None
    assert run(TgSelfGateway.ready_client(
        SimpleNamespace(TG_API_ID=0, TG_API_HASH=""),
        SimpleNamespace(has_tg=lambda c: True, tg_api=lambda: {}))) is None


def test_ready_client_authorized(monkeypatch):
    cfg = SimpleNamespace(TG_API_ID=11, TG_API_HASH="h", SESSION_PATH="/s")
    store = SimpleNamespace(has_tg=lambda c: True, tg_api=lambda: {})
    fake = FakeSelfTgClient(authorized=True)
    monkeypatch.setattr(TgSelfSession, "build", staticmethod(lambda *a: fake))
    assert run(TgSelfGateway.ready_client(cfg, store)) is fake


def test_probe_reads_last_message_both_paths():
    assert run(TgSelfGateway.probe(FakeSelfTgClient(), -100)) == (True, "✔ دسترسی دارد")
    assert run(TgSelfGateway.probe(
        FakeSelfTgClient(fail_get_messages=True), -100))[0] is True

    class Boom:
        async def get_messages(self, *a, **k):
            raise RuntimeError("no access")

    ok, note = run(TgSelfGateway.probe(Boom(), -100))
    assert not ok and "no access" in note


def test_normalize_username():
    n = TgSelfGateway.normalize_username
    assert n("@mychan") == "mychan"
    assert n("https://t.me/mychan") == "mychan"
    assert n("mychan") == "mychan"
    assert n("  @ab ") == "ab"


# ───────────────────────────── موتور ورود ─────────────────────────────

def _engine(monkeypatch, authorized=False):
    eng = TgLoginEngine(SimpleNamespace(TG_API_ID=0, TG_API_HASH="", SESSION_PATH="/s"),
                        SimpleNamespace(tg_api=lambda: {"api_id": 7, "api_hash": "h"}))
    fake = FakeSelfTgClient(authorized=authorized)
    monkeypatch.setattr(TgSelfSession, "build", staticmethod(lambda *a: fake))
    return eng, fake


def test_request_code_requires_credentials():
    eng = TgLoginEngine(SimpleNamespace(TG_API_ID=0, TG_API_HASH=""), None)
    ok, info = run(eng.request_code(1, "+98912"))
    assert not ok and "api_id/api_hash" in info


def test_request_code_success_stores_pending(monkeypatch):
    eng, fake = _engine(monkeypatch)
    ok, info = run(eng.request_code(1, "+98912"))
    assert ok and info == "کد ارسال شد"
    assert fake.calls.count("code") == 1 and eng.pending(1)
    assert eng._pending[1]["code_hash"] == "HASH1"


def test_request_code_skips_when_already_authorized(monkeypatch):
    eng, fake = _engine(monkeypatch, authorized=True)
    ok, _ = run(eng.request_code(1, "+98912"))
    assert ok and "code" not in fake.calls


def test_sign_in_success_clears_pending(monkeypatch):
    eng, fake = _engine(monkeypatch)
    run(eng.request_code(1, "+98912"))
    ok, label = run(eng.sign_in(1, "12345"))
    assert ok and label == "@selfuser"
    assert fake.disconnects == 1 and not eng.pending(1)


def test_sign_in_wrong_code_keeps_pending(monkeypatch):
    eng, fake = _engine(monkeypatch)
    run(eng.request_code(1, "+98912"))
    ok, info = run(eng.sign_in(1, "bad"))
    assert not ok and "phone-code-invalid" in info
    assert eng.pending(1)


def test_sign_in_need_password_keeps_client(monkeypatch):
    eng, _ = _engine(monkeypatch)
    run(eng.request_code(1, "+98912"))
    ok, info = run(eng.sign_in(1, "2fa"))
    assert ok == "need_password" and info == ""
    assert eng.pending(1)  # همان کلاینت برای مرحلهٔ رمز


def test_password_success(monkeypatch):
    eng, fake = _engine(monkeypatch)
    run(eng.request_code(1, "+98912"))
    run(eng.sign_in(1, "2fa"))
    ok, label = run(eng.password(1, "s3cret"))
    assert ok and label == "@selfuser" and not eng.pending(1)


def test_password_wrong_keeps_pending(monkeypatch):
    eng, _ = _engine(monkeypatch)
    run(eng.request_code(1, "+98912"))
    run(eng.sign_in(1, "2fa"))
    ok, info = run(eng.password(1, "wrongpw"))
    assert not ok and eng.pending(1)


def test_missing_pending_messages():
    eng = TgLoginEngine(SimpleNamespace(TG_API_ID=1, TG_API_HASH="h"))
    assert run(eng.sign_in(9, "1")) == (False, "نشست از دست رفت — از اول (دکمه 📱)")
    assert run(eng.password(9, "x")) == (False, "نشست از دست رفت")


def test_first_name_fallback_without_username(monkeypatch):
    eng, fake = _engine(monkeypatch)
    fake.me = SimpleNamespace(username=None, first_name="پرهام")
    run(eng.request_code(1, "+98912"))
    ok, label = run(eng.sign_in(1, "12345"))
    assert ok and label == "پرهام"


# ───────────────────────────── روتر و رویدادها ─────────────────────────────

def _router(client=None):
    bridge, admin = FakeBridge(), FakeAdmin()
    router = TgEventRouter(bridge, admin=admin, my_tg_id=123)
    return router, bridge, admin


def test_new_in_saved_messages_goes_to_admin():
    client = FakeSelfTgClient()
    router, bridge, admin = _router()
    run(router.on_new(event(tg_msg(123, "/status"), client=client)))
    assert admin.calls == [("tg", 123, 123, "/status")]
    assert not bridge.new                      # پل در کار نیست
    assert client.sent and client.sent[0][1] == "پاسخ پنل"  # پاسخ پنل ارسال شد


def test_new_saved_messages_forward_without_text_still_admin():
    client = FakeSelfTgClient()
    router, bridge, admin = _router()
    run(router.on_new(event(tg_msg(123, None, forward=object()), client=client)))
    assert len(admin.calls) == 1


def test_admin_reply_sent_without_link_preview():
    client = FakeSelfTgClient()
    router, _, admin = _router()
    run(router.on_new(event(tg_msg(123, "/list"), client=client)))
    assert client.sent and client.sent[0][0] == 123 and client.sent[0][1] == "پاسخ پنل"
    assert client.sent[0][2].get("link_preview") is False


def test_new_channel_message_goes_to_bridge():
    client = FakeSelfTgClient()
    router, bridge, admin = _router()
    m = tg_msg(-100123, "پست کانال")
    run(router.on_new(event(m, client=client)))
    assert bridge.new == [m] and not admin.calls


def test_edit_and_delete_routing():
    router, bridge, admin = _router()
    run(router.on_edit(event(tg_msg(-100, "ویرایش"))))
    assert len(bridge.edit) == 1
    run(router.on_edit(event(tg_msg(123, "ویرایش پنل"))))       # ذخیره‌شده → نادیده
    assert len(bridge.edit) == 1
    run(router.on_delete(event(chat_id=None, deleted_ids=[1])))  # بدون چت → نادیده
    run(router.on_delete(event(chat_id=123, deleted_ids=[2])))   # پنل → نادیده
    run(router.on_delete(event(chat_id=-100, deleted_ids=[3, 4])))
    assert bridge.delete == [(-100, [3, 4])]


def test_events_engine_registers_three_handlers_and_swallows_errors():
    client = FakeSelfTgClient()
    router, bridge, admin = _router()
    TgSelfBot(client, bridge, admin=admin, my_tg_id=123).register()
    names = sorted(n for n, _ in client.handlers)
    assert names == ["MessageDeleted", "MessageEdited", "NewMessage"]
    # استثنا در روتر نباید بیرون بیفتد
    async def boom(self):  # noqa: ANN001
        raise RuntimeError("x")
    router.on_new = boom.__get__(router)
    h = next(h for n, h in client.handlers if n == "NewMessage")
    run(h(event(tg_msg(1, "x"), client=client)))  # نباید raise کند


def test_module_level_register_compat():
    client = FakeSelfTgClient()
    bridge, admin = FakeBridge(), FakeAdmin()
    register(client, bridge, admin, 123)
    assert len(client.handlers) == 3

# ───── شناسهٔ نشان‌دار تلگتون → خالص (رگرسیون v2.17.6: TG→Bale بی‌صدا) ─────

def test_bare_chat_id_forms():
    assert bare_chat_id(-1003815616564) == 3815616564    # کانال نشان‌دار
    assert bare_chat_id(-1001234567890) == 1234567890
    assert bare_chat_id(3815616564) == 3815616564        # خالص → دست‌نخورده
    assert bare_chat_id(-12345) == -12345                # گروه قدیمی → دست‌نخورده
    assert bare_chat_id(-100) == -100                    # خارج از بازهٔ نشان‌دار
    assert bare_chat_id("-1003815616564") == 3815616564  # رشته‌ای
    assert bare_chat_id(None) == 0
    assert bare_chat_id("x") == 0


def test_router_delete_normalizes_marked_chat_id():
    router, bridge, _ = _router()
    run(router.on_delete(event(chat_id=-1003815616564, deleted_ids=[7])))
    assert bridge.delete == [(3815616564, [7])]
