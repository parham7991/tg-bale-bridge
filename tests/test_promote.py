"""تست‌های ادمین‌کردن ربات توسط سلف بله: BaleUserAPI.add_admin + ویزارد + /promote."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bridge.bale import BaleUserAPI
from bridge.bot_api import BotAPIError
from bridge.db import DB
from bridge.store import Store
from bridge.wizard import Wizard
from tests.conftest import run
from tests.test_wizard import FakeBaleSetup, FakeCtrl


@pytest.fixture
def ctrl():
    return FakeCtrl()


class FakePromoteClient:
    """aiobale قلابی با متدهای invite/make_user_admin."""

    def __init__(self, deny_admin=False):
        self.calls = []
        self.deny_admin = deny_admin

    async def start(self, run_in_background=False, signal_handling=True, phone_number=None):
        pass

    async def stop(self):
        pass

    async def get_me(self):
        return SimpleNamespace(id=900, name="سلف", username="selfuser")

    async def search_username(self, username):
        return SimpleNamespace(user=SimpleNamespace(id=654, name="ربات بله",
                                                    username=username, access_hash=42))

    async def invite_user(self, chat_id, user):
        self.calls.append(("invite_user", chat_id, getattr(user, "id", user)))
        return SimpleNamespace(ok=True)

    async def make_user_admin(self, chat_id, user_id, admin_name=None):
        if self.deny_admin:
            raise RuntimeError("YOU_ARE_NOT_ADMIN")
        self.calls.append(("make_user_admin", chat_id, user_id, admin_name))
        return SimpleNamespace(ok=True)

    async def get_full_group(self, cid):
        return SimpleNamespace(group_type="CHANNEL", title="کانال", username="ch")


def make_api(tmp_path, fake=None):
    fake = fake or FakePromoteClient()
    api = BaleUserAPI(db=DB(tmp_path / "d.db"), client=fake)
    return api, fake


class TestAddAdmin:
    def test_invite_then_promote(self, tmp_path):
        api, fake = make_api(tmp_path)
        res = run(api.add_admin(123, "@balehelper"))
        assert res == {"ok": True, "chat_id": 123, "user_id": 654}
        kinds = [c[0] for c in fake.calls]
        assert kinds == ["invite_user", "make_user_admin"]
        # کاربر با آبجکت search شده فرستاده شده (access_hash دارد)
        assert fake.calls[0][2] == 654
        assert fake.calls[1][2] == 654

    def test_by_numeric_id(self, tmp_path):
        api, fake = make_api(tmp_path)
        run(api.add_admin(123, 777))
        assert fake.calls[0] == ("invite_user", 123, 777)
        assert fake.calls[1] == ("make_user_admin", 123, 777, None)

    def test_already_member_ignored(self, tmp_path):
        api, fake = make_api(tmp_path)

        async def invite(chat_id, user):
            fake.calls.append(("invite_user", chat_id))
            raise RuntimeError("USER_ALREADY_MEMBER")

        fake.invite_user = invite
        res = run(api.add_admin(123, "@balehelper"))
        assert res["ok"] is True
        assert any(c[0] == "make_user_admin" for c in fake.calls)

    def test_denied_raises_botapierror(self, tmp_path):
        api, _ = make_api(tmp_path, FakePromoteClient(deny_admin=True))
        with pytest.raises(BotAPIError):
            run(api.add_admin(123, "@balehelper"))

    def test_private_chat_rejected(self, tmp_path):
        api, _ = make_api(tmp_path)
        api._chat_types["5"] = "private"
        with pytest.raises(BotAPIError):
            run(api.add_admin(5, "@balehelper"))


class TestWizardPromote:
    def _ready(self, db, cfg, ctrl):
        st = Store(db)
        st.claim_admin(555, "parham")
        st.set_bale_self("+98919")
        st.set_bale_bot("42:tok", {"id": 654, "username": "balehelper"})
        db.add_pair(-100123, "کانال تی‌جی", "tgch", 4321, "کانال بله", "balepub", "both")
        w = Wizard(ctrl, db, cfg, st)
        return w, st

    def test_promote_reports_success_and_send_test(self, ctrl, db, cfg):
        w, _ = self._ready(db, cfg, ctrl)
        bale = FakeBaleSetup(ok=True)

        async def add_admin(chat, user, admin_name=None):
            return {"ok": True, "chat_id": chat, "user_id": 654}

        bale.add_admin = add_admin

        async def _bale_user_api():
            return bale

        async def _bale_bot_api():
            return FakeBaleSetup(ok=True)

        w._bale_user_api = _bale_user_api
        w._bale_bot_api = _bale_bot_api
        run(w.handle_callback({"id": "c10", "data": "wiz:promote",
                               "message": {"chat": {"id": 10}}}))
        out = ctrl.last_text()
        assert "ادمین" in out and "✔" in out and "تست ارسال" in out

    def test_promote_failure_reported(self, ctrl, db, cfg):
        w, _ = self._ready(db, cfg, ctrl)
        bale = FakeBaleSetup(ok=False)

        async def add_admin(chat, user, admin_name=None):
            raise BotAPIError("YOU_ARE_NOT_ADMIN")

        bale.add_admin = add_admin

        async def _bale_user_api():
            return bale

        w._bale_user_api = _bale_user_api
        run(w.handle_callback({"id": "c11", "data": "wiz:promote",
                               "message": {"chat": {"id": 10}}}))
        assert "✘" in ctrl.last_text()

    def test_promote_needs_self(self, ctrl, db, cfg):
        st = Store(db)
        st.claim_admin(555, "parham")
        w = Wizard(ctrl, db, cfg, st)
        run(w.handle_callback({"id": "c12", "data": "wiz:promote",
                               "message": {"chat": {"id": 10}}}))
        assert "سلف بله" in ctrl.last_text()


class TestAdminPromoteCommand:
    def test_bot_mode_hint(self, admin):
        out = run(admin.handle("tgbot", 5, 777, "/promote @somebot"))
        assert "سلف" in out and "BALE_MODE=user" in out

    def test_help_mentions_promote(self, admin):
        assert "/promote" in run(admin.handle("tgbot", 5, 777, "/help"))
