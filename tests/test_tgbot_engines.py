"""تست‌های بستهٔ بات تلگرام (bridge/tgbot) — آفلاین با فیک‌های کامل."""
from __future__ import annotations

from types import SimpleNamespace

from bridge.tgbot import TgAdminBot
from bridge.tgbot.claim import ClaimEngine
from bridge.tgbot.guards import GuardsEngine
from bridge.tgbot.session import TgBotSession
from bridge.tgbot.types_map import OWNER_LOCKED_MSG
from tests.conftest import run

# ───────────────────────────── فیک‌ها ─────────────────────────────

class FakeAPI:
    def __init__(self):
        self.me = {"id": 777, "username": "ctrlbot", "first_name": "کنترل"}
        self.sent = []          # (chat_id, text)
        self.listen_args = None

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}

    async def get_me(self):
        return dict(self.me)

    async def listen(self, handler, offset=None, timeout=None):
        self.listen_args = (handler, offset, timeout)


class FakeDB:
    def __init__(self):
        self.meta = {}

    def get_meta(self, k):
        return self.meta.get(k)

    def set_meta(self, k, v):
        self.meta[k] = v


class FakeStore:
    def __init__(self, claimable=True):
        self.claimable = claimable
        self.claimed = None

    def claim_admin(self, uid, username):
        if not self.claimable:
            return False
        self.claimed = (uid, username)
        return True


class FakeWizard:
    def __init__(self):
        self.opened = []
        self.texts = []
        self.callbacks = []
        self.active_chats = set()

    def is_active(self, chat_id):
        return chat_id in self.active_chats

    async def open(self, chat_id, uid):
        self.opened.append((chat_id, uid))

    async def handle_text(self, chat_id, uid, text, msg):
        self.texts.append((chat_id, uid, text))

    async def handle_callback(self, cb):
        self.callbacks.append(cb)


class FakeAdmin:
    def __init__(self):
        self.calls = []

    async def handle(self, platform, chat_id, uid, text, msg):
        self.calls.append((platform, chat_id, uid, text))
        return "پاسخ پنل"


def msg(text="", chat_type="private", uid=555, username="ali", **extra):
    m = {"message_id": 1, "chat": {"id": 100, "type": chat_type},
         "from": {"id": uid, "username": username}, "text": text}
    m.update(extra)
    return m


def make_bot(admin=True, wizard=True, store=True, claimable=True, admin_id=0):
    api, db = FakeAPI(), FakeDB()
    cfg = SimpleNamespace(ADMIN_TG_ID=admin_id)
    f_admin = FakeAdmin() if admin else None
    f_wiz = FakeWizard() if wizard else None
    f_store = FakeStore(claimable) if store else None
    bot = TgAdminBot(api, f_admin, db, cfg, wizard=f_wiz, store=f_store)
    return bot, api, db, cfg, f_admin, f_wiz, f_store


# ───────────────────────────── نشست ─────────────────────────────

def test_session_identify_stores_me():
    api = FakeAPI()
    s = TgBotSession(api, FakeDB())
    me = run(s.identify())
    assert me["username"] == "ctrlbot" and s.me["id"] == 777


def test_session_offset_roundtrip():
    db = FakeDB()
    s = TgBotSession(FakeAPI(), db)
    assert s.offset() is None
    s.save_offset(41)
    assert s.offset() == 41 and db.meta["tgbot_offset"] == "41"


def test_facade_start_sets_identity_and_listen():
    bot, api, db, cfg, f_admin, *_ = make_bot(admin_id=900)
    run(bot.start())
    assert f_admin.tg_bot_info["username"] == "ctrlbot"
    handler, offset, timeout = api.listen_args
    assert handler == bot.on_update and offset is None and timeout == 30
    # آفست پس از یک آپدیت ذخیره می‌شود
    run(handler({"message": msg()}, 12))
    assert db.meta["tgbot_offset"] == "12"


# ───────────────────────────── مسیریابی ─────────────────────────────

def test_callback_query_goes_to_wizard():
    bot, api, db, *_, f_wiz, _ = make_bot()
    cb = {"id": "c1", "data": "wiz:menu", "message": {"chat": {"id": 100}}}
    run(bot.on_update({"callback_query": cb}, 5))
    assert f_wiz.callbacks == [cb] and db.meta["tgbot_offset"] == "5"
    assert not api.sent


def test_non_private_message_ignored():
    bot, api, *_ = make_bot(admin_id=900)
    run(bot.on_update({"message": msg(chat_type="group")}, 1))
    assert not api.sent


def test_empty_text_without_forward_ignored():
    bot, api, *_ = make_bot(admin_id=900)
    run(bot.on_update({"message": msg(), "photo": {"x": 1}}, 1))
    run(bot.on_update({"message": msg("", photo={"x": 1})}, 1))
    assert not api.sent


def test_forward_without_text_reaches_admin():
    bot, api, _, _, f_admin, f_wiz, _ = make_bot(admin_id=900)
    run(bot.on_update({"message": msg(forward_from_chat={"id": -100})}, 1))
    assert f_admin.calls and f_wiz.opened == []


def test_exception_is_swallowed_and_logged(monkeypatch):
    bot, *_ = make_bot()
    async def boom(cb):
        raise RuntimeError("x")
    bot.router.wizard.handle_callback = boom
    run(bot.on_update({"callback_query": {"id": "c"}}, 1))  # نباید raise کند


# ───────────────────────────── ادمین خودکار ─────────────────────────────

def test_first_start_claims_admin_and_opens_wizard():
    bot, api, _, cfg, _, f_wiz, f_store = make_bot(admin_id=0)
    handled = run(bot.on_update({"message": msg("/start", uid=555)}, 1))
    assert f_store.claimed == (555, "ali") and cfg.ADMIN_TG_ID == 555
    assert any("ادمین پل شدید" in t for _, t in api.sent)
    assert f_wiz.opened == [(100, 555)]


def test_claim_refused_when_store_says_taken():
    bot, api, _, cfg, *_ = make_bot(admin_id=0, claimable=False)
    run(bot.on_update({"message": msg("/start")}, 1))
    assert api.sent and OWNER_LOCKED_MSG in api.sent[-1][1]
    assert not getattr(cfg, "ADMIN_TG_ID", 0)


def test_no_admin_any_message_gets_lock_msg():
    bot, api, *_ = make_bot(admin_id=0, store=True)
    run(bot.on_update({"message": msg("سلام")}, 1))
    assert OWNER_LOCKED_MSG in api.sent[-1][1]


def test_claim_engine_not_applicable_with_admin():
    e = ClaimEngine(FakeAPI(), SimpleNamespace(ADMIN_TG_ID=1), store=FakeStore())
    assert e.applicable() is False
    assert run(e.handle(1, 2, "u", "/start")) is False


# ───────────────────────────── ویزارد و نگهبان‌ها ─────────────────────────────

def test_admin_setup_text_opens_wizard():
    bot, api, _, _, _, f_wiz, _ = make_bot(admin_id=555)
    for t in ("/setup", "نصب", "/start"):
        run(bot.on_update({"message": msg(t)}, 1))
    assert len(f_wiz.opened) == 3


def test_active_wizard_receives_text():
    bot, api, _, _, _, f_wiz, _ = make_bot(admin_id=555)
    f_wiz.active_chats.add(100)
    run(bot.on_update({"message": msg("+98912")}, 1))
    assert f_wiz.texts == [(100, 555, "+98912")]
    assert not api.sent  # پیام به پنل ادمین نرفته


def test_non_admin_start_gets_locked():
    bot, api, *_ = make_bot(admin_id=900)
    run(bot.on_update({"message": msg("/start", uid=777, username="bad")}, 1))
    assert OWNER_LOCKED_MSG in api.sent[-1][1]


def test_admin_panel_reply_sent():
    bot, api, _, _, f_admin, *_ = make_bot(admin_id=900)
    run(bot.on_update({"message": msg("/list")}, 1))
    assert f_admin.calls == [("tgbot", 100, 555, "/list")]
    assert ("100", ) == () or api.sent[-1] == (100, "پاسخ پنل")


def test_admin_none_silent():
    bot, api, *_ = make_bot(admin=None, admin_id=900)
    run(bot.on_update({"message": msg("/list")}, 1))
    assert not api.sent


# ───────────────────────────── نگهبان و سازگاری ─────────────────────────────

def test_guards_is_admin():
    g = GuardsEngine(SimpleNamespace(ADMIN_TG_ID=900))
    assert g.is_admin(900) and not g.is_admin(901) and not g.is_admin(None)


def test_facade_compat_surface():
    bot, *_ = make_bot(admin_id=900)
    assert bot._is_admin(900) and not bot._is_admin(5)
    assert bot.me == {} and bot.api is bot.router.api
    assert isinstance(bot.session, TgBotSession)
