"""تست‌های نصاب: Store + ویزارد داخل بات تلگرام + مسیریابی TgAdminBot + /access."""
from __future__ import annotations

import pytest

from bridge.bot_api import BotAPIError
from bridge.store import Store
from bridge.tg_bot import TgAdminBot
from bridge.wizard import Wizard, probe_bale_access, probe_tg_access
from tests.conftest import run


class FakeCtrl:
    """بات کنترل قلابی — پیام‌ها و callها را ضبط می‌کند."""

    def __init__(self):
        self.sent = []      # (chat_id, text, reply_markup)
        self.calls = []

    async def send_message(self, chat_id, text, reply_to=None, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    async def call(self, method, params=None, files=None):
        self.calls.append((method, params))
        return {}

    async def get_me(self):
        return {"id": 1, "username": "ctrl"}

    def last_text(self):
        return self.sent[-1][1] if self.sent else ""


class FakeSelfTg:
    """کلاینت سلف تلگرام قلابی برای resolve/probe."""

    async def get_entity(self, ref):
        class E:
            id = -100123
            title = "کانال تی‌جی"
            username = "tgpub"

        return E()

    async def get_messages(self, entity, limit=1):
        return [object()]


class FakeBaleSetup:
    """سمت بله قلابی برای resolve/probe ویزارد."""

    def __init__(self, ok=True):
        self.ok = ok
        self.deleted = []

    async def get_chat(self, ref):
        if not self.ok:
            raise BotAPIError("not found")
        return {"id": 4321, "type": "channel", "title": "کانال بله", "username": "balepub"}

    async def send_message(self, chat_id, text, reply_to=None, **kw):
        if not self.ok:
            raise BotAPIError("forbidden")
        return {"message_id": 777}

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return {"ok": True}


@pytest.fixture
def ctrl():
    return FakeCtrl()


@pytest.fixture
def wizard(ctrl, db, cfg):
    w = Wizard(ctrl, db, cfg, Store(db))
    # مرزهای I/O با فیک — FSM و منطق واقعی تست می‌شوند
    w._tg_client = run  # placeholder replaced below
    return w


def _stub_io(w, tg_client=None, bale_api=None, bot_api=None):
    async def _tg_client():
        return tg_client

    async def _bale_user_api():
        return None

    async def _bale_api_for_setup():
        return bale_api

    def _bale_bot_api():
        return bot_api

    async def _tg_request_code(chat_id, phone):
        return True, "کد ارسال شد"

    async def _tg_sign_in(chat_id, code):
        return True, "@newself"

    async def _bale_request_code(phone):
        return True, "کد ارسال شد"

    async def _bale_validate(chat_id, code):
        return True, "نشست ذخیره شد"

    async def _check_bale_bot(token):
        return True, {"id": 5, "username": "balehelper"}

    w._tg_client = _tg_client
    w._bale_user_api = _bale_user_api
    w._bale_api_for_setup = _bale_api_for_setup
    w._bale_bot_api = _bale_bot_api
    w._tg_request_code = _tg_request_code
    w._tg_sign_in = _tg_sign_in
    w._bale_request_code = _bale_request_code
    w._bale_validate = _bale_validate
    w._check_bale_bot = _check_bale_bot


# ───────────────────────────── Store ─────────────────────────────

class TestStore:
    def test_roundtrip(self, db):
        st = Store(db)
        st.set("x", {"a": 1, "ب": "متن"})
        assert st.get("x") == {"a": 1, "ب": "متن"}
        assert st.get("missing", 7) == 7

    def test_claim_admin_once(self, db):
        st = Store(db)
        assert st.claim_admin(555, "parham") is True
        assert st.admin_tg_id() == 555
        assert st.claim_admin(666, "other") is False
        assert st.admin_tg_id() == 555

    def test_installed_flags(self, db, cfg):
        st = Store(db)
        assert not st.has_tg(cfg)
        assert not st.has_bale(cfg)
        assert not st.installed(cfg)
        st.set_bale_bot("1:AA", {"id": 1})
        assert st.has_bale(cfg)
        assert st.bale_bot()["token"] == "1:AA"


# ───────────────────────────── ویزارد: FSM ─────────────────────────────

class TestWizardTgSelf:
    def test_full_tg_flow(self, wizard, cfg, db, ctrl):
        st = Store(db)
        run(wizard.handle_text(10, 10, "12345", None))  # state=tg_api_id? نه — منو است
        # مستقیم به حالت اول برویم مثل دکمه wiz:tg
        run(wizard.handle_callback({"id": "c1", "data": "wiz:tg",
                                    "message": {"chat": {"id": 10}}}))
        assert wizard._state(10)["state"] == "tg_api_id"
        run(wizard.handle_text(10, 10, "12345", None))
        assert wizard._state(10)["state"] == "tg_api_hash"
        run(wizard.handle_text(10, 10, "deadbeef" * 4, None))
        assert wizard._state(10)["state"] == "tg_phone"
        assert st.tg_api() == {"api_id": 12345, "api_hash": "deadbeef" * 4}
        _stub_io(wizard)  # مرز I/O از قبل از مرحله شماره استاب می‌شود
        run(wizard.handle_text(10, 10, "+989120000000", None))
        assert wizard._state(10)["state"] == "tg_code"
        run(wizard.handle_text(10, 10, "55555", None))
        assert wizard._state(10)["state"] == "menu"
        assert st.tg_self() == {"phone": "+989120000000"}
        assert any("✅ سلف تلگرام" in t for _, t, _ in ctrl.sent)


class TestWizardBale:
    def test_bale_self_flow(self, wizard, db, ctrl):
        st = Store(db)
        run(wizard.handle_callback({"id": "c2", "data": "wiz:bale",
                                    "message": {"chat": {"id": 10}}}))
        assert wizard._state(10)["state"] == "bale_phone"
        _stub_io(wizard)
        run(wizard.handle_text(10, 10, "+989190000000", None))
        assert wizard._state(10)["state"] == "bale_code"
        run(wizard.handle_text(10, 10, "74200", None))
        assert wizard._state(10)["state"] == "menu"
        assert st.bale_self() == {"phone": "+989190000000"}

    def test_bale_bot_token_flow(self, wizard, db):
        st = Store(db)
        run(wizard.handle_callback({"id": "c3", "data": "wiz:bbot",
                                    "message": {"chat": {"id": 10}}}))
        assert wizard._state(10)["state"] == "bbot_token"
        _stub_io(wizard)
        run(wizard.handle_text(10, 10, "42:ABC-TOKEN", None))
        assert wizard._state(10)["state"] == "menu"
        assert st.bale_bot()["me"]["username"] == "balehelper"


# ───────────────────────────── ویزارد: جفت کانال ─────────────────────────────

class TestWizardPairing:
    def _setup_accounts(self, w, db, cfg):
        st = Store(db)
        st.set_tg_api(1, "h")
        st.set_tg_self("+98912")
        st.set_bale_self("+98919")
        cfg.TG_API_ID, cfg.TG_API_HASH = 1, "h"

    def test_pair_flow_with_callbacks(self, wizard, db, cfg):
        self._setup_accounts(wizard, db, cfg)
        _stub_io(wizard, tg_client=FakeSelfTg(), bale_api=FakeBaleSetup())
        run(wizard.handle_callback({"id": "c4", "data": "wiz:pair",
                                    "message": {"chat": {"id": 10}}}))
        assert wizard._state(10)["state"] == "pair_tg"
        # مرحله ۱: کانال تلگرام با @username (resolve با سلف)
        run(wizard.handle_text(10, 10, "@tgpub", None))
        assert wizard._state(10)["state"] == "pair_bale"
        # مرحله ۲: کانال بله
        run(wizard.handle_text(10, 10, "@balepub", None))
        assert wizard._state(10)["state"] == "pair_dir"
        # جهت با دکمه
        run(wizard.handle_callback({"id": "c5", "data": "wiz:dir:both",
                                    "message": {"chat": {"id": 10}}}))
        assert wizard._state(10)["state"] == "menu"
        pairs = wizard.db.list_pairs()
        assert len(pairs) == 1
        assert pairs[0]["tg_chat_id"] == -100123
        assert int(pairs[0]["bale_chat_id"]) == 4321
        assert pairs[0]["mode"] == "both"
        # گزارش دسترسی در پاسخ آمده
        assert any("دسترسی" in t for _, t, _ in wizard.api.sent)

    def test_pair_tg_forward(self, wizard, db, cfg):
        self._setup_accounts(wizard, db, cfg)
        _stub_io(wizard, bale_api=FakeBaleSetup())
        msg = {"forward_from_chat": {"id": -100777, "title": "فرواردی", "username": "fwdch"}}
        run(wizard.handle_text(10, 10, "", msg))
        assert wizard._state(10)["state"] == "pair_bale"
        run(wizard.handle_text(10, 10, "@balepub", None))
        run(wizard.handle_callback({"id": "c6", "data": "wiz:dir:tg2bale",
                                    "message": {"chat": {"id": 10}}}))
        pair = wizard.db.list_pairs()[0]
        assert pair["tg_chat_id"] == -100777 and pair["mode"] == "tg2bale"

    def test_pair_without_bale_account(self, wizard, db, cfg):
        self._setup_accounts(wizard, db, cfg)  # سلف تلگرام هست؛ سلف بله نه
        _stub_io(wizard, tg_client=FakeSelfTg(), bale_api=None)
        run(wizard.handle_callback({"id": "c7", "data": "wiz:pair",
                                    "message": {"chat": {"id": 10}}}))
        run(wizard.handle_text(10, 10, "@tgpub", None))    # مرحله ۱ اوکی
        run(wizard.handle_text(10, 10, "@balepub", None))  # مرحله ۲: حساب بله نیست
        out = wizard.api.last_text()
        assert "ابتدا سلف بله" in out


# ───────────────────────────── probes ─────────────────────────────

class TestProbes:
    def test_probe_tg_ok(self):
        ok, note = run(probe_tg_access(FakeSelfTg(), -100123))
        assert ok and "✔" in note

    def test_probe_bale_ok_and_fail(self):
        ok, note = run(probe_bale_access(FakeBaleSetup(ok=True), 4321))
        assert ok and "✔" in note
        ok, note = run(probe_bale_access(FakeBaleSetup(ok=False), 4321))
        assert not ok and "✘" in note


# ───────────────────────────── TgAdminBot ─────────────────────────────

class TestTgAdminBotRouting:
    def _bot(self, ctrl, db, cfg, wizard):
        return TgAdminBot(ctrl, None, db, cfg, wizard=wizard, store=Store(db))

    def test_first_start_claims_admin_and_opens_wizard(self, ctrl, db, cfg):
        cfg.ADMIN_TG_ID = 0
        w = Wizard(ctrl, db, cfg, Store(db))
        bot = self._bot(ctrl, db, cfg, w)
        run(bot.on_update({"message": {"chat": {"id": 9, "type": "private"},
                                       "from": {"id": 555, "username": "parham"},
                                       "text": "/start"}}, 1))
        assert Store(db).admin_tg_id() == 555
        assert cfg.ADMIN_TG_ID == 555
        assert any("ادمین" in t for _, t, _ in ctrl.sent)
        assert w.is_active(9)

    def test_second_user_rejected(self, ctrl, db, cfg):
        cfg.ADMIN_TG_ID = 0
        w = Wizard(ctrl, db, cfg, Store(db))
        bot = self._bot(ctrl, db, cfg, w)
        run(bot.on_update({"message": {"chat": {"id": 9, "type": "private"},
                                       "from": {"id": 555}, "text": "/start"}}, 1))
        run(bot.on_update({"message": {"chat": {"id": 8, "type": "private"},
                                       "from": {"id": 666}, "text": "/start"}}, 2))
        assert Store(db).admin_tg_id() == 555
        assert any("صاحب دارد" in t for _, t, _ in ctrl.sent)

    def test_callback_routed_to_wizard(self, ctrl, db, cfg):
        cfg.ADMIN_TG_ID = 555
        w = Wizard(ctrl, db, cfg, Store(db))
        bot = self._bot(ctrl, db, cfg, w)
        run(bot.on_update({"callback_query": {"id": "cb9", "data": "wiz:status",
                                              "message": {"chat": {"id": 9}}}}, 1))
        assert any("ویزارد" in t or "سلف" in t for _, t, _ in ctrl.sent)

    def test_setup_command_opens_wizard(self, ctrl, db, cfg):
        cfg.ADMIN_TG_ID = 555
        w = Wizard(ctrl, db, cfg, Store(db))
        bot = self._bot(ctrl, db, cfg, w)
        run(bot.on_update({"message": {"chat": {"id": 9, "type": "private"},
                                       "from": {"id": 555}, "text": "/setup"}}, 1))
        assert w.is_active(9)

    def test_active_wizard_gets_text_before_admin(self, ctrl, db, cfg):
        cfg.ADMIN_TG_ID = 555
        w = Wizard(ctrl, db, cfg, Store(db))
        bot = self._bot(ctrl, db, cfg, w)
        run(bot.on_update({"message": {"chat": {"id": 9, "type": "private"},
                                       "from": {"id": 555}, "text": "/setup"}}, 1))
        # در منو، پیام فورواردی مستقیماً جفت‌کردن را شروع می‌کند
        run(bot.on_update({"message": {"chat": {"id": 9, "type": "private"},
                                       "from": {"id": 555}, "text": "",
                                       "forward_from_chat": {"id": -100123, "title": "ت"}}}, 2))
        assert wizard_state(w, 9) == "pair_bale"


def wizard_state(w, chat_id):
    return w._state(chat_id)["state"]


# ───────────────────────────── /access در پنل ادمین ─────────────────────────────

class TestAccessCommand:
    def test_access_lists_pairs(self, admin, pair):
        out = run(admin.handle("tgbot", 5, 777, "/access"))
        assert "دسترسی" in out and "جفت #1" in out

    def test_access_empty(self, admin):
        out = run(admin.handle("tgbot", 5, 777, "/access"))
        assert "جفتی ثبت نشده" in out

    def test_help_mentions_setup_and_access(self, admin):
        out = run(admin.handle("tgbot", 5, 777, "/help"))
        assert "/access" in out and "/setup" in out
