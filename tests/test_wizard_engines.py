"""تست‌های بستهٔ ویزارد (bridge/wizard) — موتورهای منو/حساب‌ها/جفت‌کردن/پایان."""
from __future__ import annotations

from types import SimpleNamespace

from bridge.wizard import Wizard
from bridge.wizard.accounts import AccountsEngine
from bridge.wizard.finish import FinishEngine
from bridge.wizard.menu import MenuEngine
from bridge.wizard.types_map import DIR_KB, extract_token, forward_chat_info
from bridge.wizard.version import VERSION
from tests.conftest import run

# ───────────────────────────── فیک‌ها ─────────────────────────────

class FakeStore:
    def __init__(self, tg=False, bale_self=False, bale_bot=None):
        self._tg, self._bs, self._bb = tg, bale_self, bale_bot

    def has_tg(self, cfg):
        return self._tg

    def has_bale(self, cfg):
        return bool(self._bs or self._bb)

    def bale_self(self):
        return {"phone": "+98912"} if self._bs else None

    def tg_self(self):
        return {"phone": "+98910"} if self._tg else None

    def bale_bot(self):
        return self._bb

    def installed(self, cfg):
        return self._tg and self.has_bale(cfg)

    def set(self, k, v):
        pass


class FakeDB:
    def list_pairs(self):
        return [1, 2, 3]

    def add_pair(self, *a):
        return 7


class FakeSent:
    def __init__(self):
        self.sent = []

    async def __call__(self, chat_id, text, kb=None):
        self.sent.append((text, kb))


def wiz_min(store, cfg, db=None, api=None):
    """نمای حداقلی: موتورها واقعی، _send جعلی."""
    w = SimpleNamespace()
    w.db = db or FakeDB()
    w.cfg = cfg
    w.store = store
    w._send = FakeSent()
    w._menu_kb = lambda: {"inline_keyboard": [["menu"]]}
    w.menu = MenuEngine(w.db, cfg, store)
    w.accounts = AccountsEngine(w, cfg, store)
    w.reports = SimpleNamespace(report=lambda pid=None: None)
    w.finish_engine = FinishEngine(w, store, cfg)
    return w


# ───────────────────────────── types_map ─────────────────────────────

def test_forward_chat_info_old_shape():
    info = forward_chat_info({"forward_from_chat": {"id": -100, "title": "ت",
                                                    "username": "ch"}})
    assert info == {"id": -100, "title": "ت", "username": "ch"}


def test_forward_chat_info_new_origin_shape():
    info = forward_chat_info({"forward_origin": {
        "type": "chat", "chat": {"id": 55, "title": "ق", "username": "u2"}}})
    assert info["id"] == 55 and info["username"] == "u2"


def test_forward_chat_info_none():
    assert forward_chat_info({}) is None
    assert forward_chat_info(None) is None


def test_extract_token():
    assert extract_token("توکن من 42:ABC") == "42:ABC"
    assert extract_token("42:ABC") == "42:ABC"
    assert extract_token("plain") == "plain"
    assert extract_token("") == ""


# ───────────────────────────── MenuEngine ─────────────────────────────

def test_menu_kb_reflects_store_state():
    cfg = SimpleNamespace()
    st = FakeStore(tg=True, bale_self=True,
                   bale_bot={"token": "t", "me": {"username": "bb"}})
    m = MenuEngine(FakeDB(), cfg, st)
    kb = m.kb()
    flat = [b for row in kb["inline_keyboard"] for b in row]
    assert sum("✅" in b["text"] for b in flat) == 4      # ۳ وضعیت + دکمهٔ اتمام
    assert any(b["callback_data"] == "wiz:done" for b in flat)


def test_menu_text_shows_pairs_count():
    cfg = SimpleNamespace()
    m = MenuEngine(FakeDB(), cfg, FakeStore())
    txt = m.text()
    assert "جفت‌های کانال: 3" in txt and "تنظیم نشده" in txt


# ───────────────────────────── AccountsEngine ─────────────────────────────

def test_check_bale_bot_invalid_token(monkeypatch):
    import bridge.wizard.accounts as acc

    class FakeAPI:
        def __init__(self, token, base=None):
            pass

        async def get_me(self):
            raise RuntimeError("401")

        async def close(self):
            pass

    monkeypatch.setattr(acc, "BotAPI", FakeAPI)
    e = AccountsEngine(SimpleNamespace(db=None), SimpleNamespace(), FakeStore())
    ok, info = run(e.check_bale_bot("bad:tok"))
    assert not ok and "توکن نامعتبر" in info


def test_bale_bot_api_none_without_token():
    e = AccountsEngine(SimpleNamespace(db=None), SimpleNamespace(), FakeStore())
    assert e.bale_bot_api() is None


# ───────────────────────────── FinishEngine ─────────────────────────────

def test_finish_incomplete_lists_missing():
    st = FakeStore(tg=False, bale_self=False)
    w = wiz_min(st, SimpleNamespace())
    run(w.finish_engine.finish(9))
    text, kb = w._send.sent[-1]
    assert "هنوز کامل نشده" in text
    assert "سلف تلگرام" in text and "سمت بله" in text
    assert kb == {"inline_keyboard": [["menu"]]}


def test_finish_complete_triggers_restart_task(monkeypatch):
    st = FakeStore(tg=True, bale_self=True)
    w = wiz_min(st, SimpleNamespace())
    called = []

    async def fake_restart():
        called.append(True)

    monkeypatch.setattr(FinishEngine, "do_restart", staticmethod(fake_restart))
    orig_create = __import__("asyncio").create_task
    __import__("asyncio").create_task = lambda coro: coro.close() or fake_restart()
    try:
        run(w.finish_engine.finish(9))
    finally:
        __import__("asyncio").create_task = orig_create
    assert any("نصب کامل شد" in t for t, _ in w._send.sent)


# ───────────────────────────── DashInfoEngine ─────────────────────────────

def test_dashinfo_disabled():
    from bridge.wizard.dashinfo import DashInfoEngine

    w = wiz_min(FakeStore(), SimpleNamespace(DASH_ENABLED=0))
    d = DashInfoEngine(w, w.cfg, w.store)
    run(d.info(9))
    assert "خاموش است" in w._send.sent[-1][0]


def test_dashinfo_shows_address_and_one_time_password(monkeypatch):
    from bridge.dashboard import Dashboard
    from bridge.wizard.dashinfo import DashInfoEngine

    monkeypatch.setattr(Dashboard, "ensure_credentials",
                        lambda store: ("admin", "s3cret", True))
    cfg = SimpleNamespace(DASH_HOST="0.0.0.0", DASH_PORT=8080)
    d = DashInfoEngine(wiz_min(FakeStore(), cfg), cfg, FakeStore())
    run(d.info(9))
    text, kb = d.wiz._send.sent[-1]
    assert "http://<IP-سرور>:8080" in text and "s3cret" in text and kb


# ───────────────────────────── سازگاری ─────────────────────────────

def test_package_version_and_dir_kb():
    assert VERSION == "2.17.2"
    assert "dir:both" in str(DIR_KB)


def test_facade_has_full_legacy_surface():
    for name in ("_menu_kb", "_menu_text", "is_active", "_state", "_send", "_answer",
                 "open", "handle_text", "handle_callback", "_pair_begin",
                 "_pair_tg_resolve", "_pair_bale_resolve", "_pair_finish", "_dash_info",
                 "_promote_begin", "_access_report", "access_report", "_tg_client",
                 "_tg_request_code", "_tg_sign_in", "_tg_password",
                 "_bale_request_code", "_bale_validate", "_bale_bot_api",
                 "_bale_user_api", "_bale_api_for_setup", "_check_bale_bot",
                 "_finish", "_do_restart"):
        assert hasattr(Wizard, name), name

# ─────────────── رگرسیون v2.17.2: نرمال‌سازی ورودی کانال بله ───────────────

def test_normalize_bale_ref_formats():
    from bridge.wizard.pairing import normalize_bale_ref as n
    assert n("  @marvellit ") == "@marvellit"
    assert n("marvellit") == "marvellit"
    assert n("-1001234") == "-1001234"
    assert n("https://ble.ir/marvellit") == "@marvellit"
    assert n("https://ble.ir/marvellit/") == "@marvellit"
    assert n("bale.ai/@marvellit") == "@marvellit"
    assert n("https://web.bale.ai/x/@marvellit") == "@marvellit"   # سگمنت آخر
    assert n("t.me/marvellit") == "@marvellit"
    # لینک خصوصی دست‌نخورده می‌ماند (خطای راهنما می‌گیرد)
    assert n("https://ble.ir/joinchat/AbCdEf") == "https://ble.ir/joinchat/AbCdEf"
    assert n("https://ble.ir/+AbCd") == "https://ble.ir/+AbCd"
    assert n("") == ""
