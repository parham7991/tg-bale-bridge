"""تست‌های بات مدیریت تلگرام و دستورات کنترل سلف‌بات."""
from __future__ import annotations

from tests.conftest import run


class FakeLogBuffer:
    def __init__(self, lines):
        self._lines = lines

    def tail(self, n):
        return self._lines[-n:]


class TestTgBotAuth:
    def test_bootstrap_shows_id(self, admin):
        admin.cfg.ADMIN_TG_ID = 0
        out = run(admin.handle("tgbot", 5, 555, "/start"))
        assert "555" in out and "ADMIN_TG_ID" in out

    def test_non_admin_rejected(self, admin):
        assert run(admin.handle("tgbot", 5, 555, "/list")) is None

    def test_admin_allowed(self, admin, pair):
        out = run(admin.handle("tgbot", 5, 777, "/list"))
        assert "جفت" in out


class TestSelfBotCommands:
    def test_pause_resume(self, admin, bridge, db):
        out = run(admin.handle("tgbot", 5, 777, "/pause"))
        assert bridge.paused and "متوقف" in out
        assert db.get_meta("paused") == "1"
        out = run(admin.handle("tgbot", 5, 777, "/resume"))
        assert not bridge.paused and "از سر گرفته" in out
        assert db.get_meta("paused") == "0"

    def test_pause_persian_alias(self, admin, bridge):
        run(admin.handle("tgbot", 5, 777, "توقف"))
        assert bridge.paused
        run(admin.handle("tgbot", 5, 777, "ادامه"))
        assert not bridge.paused

    def test_logs(self, admin):
        admin.log_buffer = FakeLogBuffer(["خط اول", "خط دوم", "خط سوم"])
        out = run(admin.handle("tgbot", 5, 777, "/logs 2"))
        assert "خط دوم" in out and "خط سوم" in out and "خط اول" not in out

    def test_logs_empty(self, admin):
        admin.log_buffer = None
        assert "در دسترس نیست" in run(admin.handle("tgbot", 5, 777, "/logs"))

    def test_whoami(self, admin):
        admin.tg_bot_info = {"username": "ctrlbot", "id": 42}
        out = run(admin.handle("tgbot", 5, 777, "/whoami"))
        assert "777" in out and "ctrlbot" in out and "mirbot" in out and "selfuser" in out

    def test_status_shows_state(self, admin, bridge, db):
        bridge.paused = True
        out = run(admin.handle("tgbot", 5, 777, "/status"))
        assert "متوقف" in out and "mirbot" in out
        bridge.paused = False
        out = run(admin.handle("tgbot", 5, 777, "/status"))
        assert "همگام‌سازی" in out and "متوقف" not in out
        assert "جفت‌های کانال" in out


class TestForwardOrigin:
    def test_channel_origin(self, admin):
        msg = {"forward_origin": {
            "type": "channel",
            "chat": {"id": 55, "title": "کانال خصوصی", "username": None},
            "message_id": 3,
        }}
        out = run(admin.handle("tgbot", 5, 777, "", msg))
        assert "55" in out and "کانال خصوصی" in out

    def test_user_origin(self, admin):
        msg = {"forward_origin": {
            "type": "user",
            "sender_user": {"id": 88, "first_name": "علی", "username": "ali"},
        }}
        out = run(admin.handle("tgbot", 5, 777, "", msg))
        assert "88" in out and "ali" in out

    def test_hidden_user_origin(self, admin):
        msg = {"forward_origin": {"type": "hidden_user", "sender_user_name": "ناشناس"}}
        out = run(admin.handle("tgbot", 5, 777, "", msg))
        assert "ناشناس" in out

    def test_classic_forward_still_works(self, admin):
        msg = {"forward_from_chat": {"id": 55, "title": "کانال", "username": "ch"}}
        out = run(admin.handle("tgbot", 5, 777, "", msg))
        assert "55" in out
