"""تست‌های دستورات مدیریتی (پنل داخل ربات بله / Saved Messages)."""
from __future__ import annotations

from tests.conftest import run


class TestAuth:
    def test_bootstrap_shows_id(self, admin, cfg):
        cfg_id = admin.cfg
        cfg_id.ADMIN_BALE_ID = 0
        out = run(admin.handle("bale", 123, 123, "/start"))
        assert "123" in out and "ADMIN_BALE_ID" in out

    def test_non_admin_rejected(self, admin):
        assert run(admin.handle("bale", 42, 999, "/list")) is None

    def test_admin_allowed(self, admin, pair):
        assert "جفت" in run(admin.handle("bale", 42, 42, "/list"))


class TestCommands:
    def test_add_list_mode_remove(self, admin):
        out = run(admin.handle("bale", 42, 42, "/add @tgch 777 both"))
        assert "ثبت شد" in out and "دوطرفه" in out
        out = run(admin.handle("bale", 42, 42, "/list"))
        assert "کانال تی‌جی" in out and "کانال بله" in out
        out = run(admin.handle("bale", 42, 42, "/mode 1 tg2bale"))
        assert "تلگرام→بله" in out
        out = run(admin.handle("bale", 42, 42, "/remove 1"))
        assert "حذف شد" in out

    def test_add_bad_mode(self, admin):
        out = run(admin.handle("bale", 42, 42, "/add @tgch 777 weird"))
        assert "نامعتبر" in out

    def test_add_unknown_channel(self, admin):
        out = run(admin.handle("bale", 42, 42, "/add @nope 777"))
        assert "پیدا نشد" in out

    def test_test_command(self, admin, pair):
        out = run(admin.handle("bale", 42, 42, f"/test {pair}"))
        assert "نتیجه تست" in out and "بله ✔" in out and "تلگرام ✔" in out

    def test_status(self, admin, pair):
        out = run(admin.handle("bale", 42, 42, "/status"))
        assert "وضعیت" in out and "mirbot" in out

    def test_help(self, admin):
        assert "/add" in run(admin.handle("bale", 42, 42, "/help"))

    def test_unknown_command(self, admin):
        assert "ناشناخته" in run(admin.handle("bale", 42, 42, "/whatever"))


class TestIdDiscovery:
    def test_forwarded_bale_channel(self, admin):
        out = run(admin.handle("bale", 42, 42, "چیزی",
                               {"forward_from_chat": {"id": 55, "title": "کانال خصوصی"}}))
        assert "55" in out and "کانال خصوصی" in out

    def test_forwarded_tg_channel(self, admin):
        class Msg:
            forward = None
        import datetime

        from telethon import types as tg_t

        class M:
            forward = tg_t.MessageFwdHeader(
                date=datetime.datetime.now(), from_id=tg_t.PeerChannel(channel_id=1234),
                from_name=None, channel_post=1, post_author=None,
            )
        out = run(admin.handle("tg", 999, 999, "", M()))
        assert "1234" in out or "-1000000001234" in out

    def test_no_forward_gives_minimal_help(self, admin):
        assert "پل" in run(admin.handle("bale", 42, 42, "سلام چی کار کنم؟"))


class TestSurfaces:
    """پنل چهارسطحی — حالت‌آگاهی سلف‌بات/ربات."""

    def test_whoami_user_mode(self, admin, cfg):
        cfg.BALE_MODE = "user"
        cfg.BALE_TOKEN = "x"
        out = run(admin.handle("bale", 42, 42, "/whoami"))
        assert "سلف‌بات" in out and "پنل" in out and "خودچت" in out and "ربات بله" in out

    def test_whoami_bot_mode(self, admin, cfg):
        out = run(admin.handle("bale", 42, 42, "/whoami"))
        assert "ربات بله" in out and "خودچت" not in out

    def test_status_user_mode_two_way_delete(self, admin, cfg, pair):
        cfg.BALE_MODE = "user"
        out = run(admin.handle("bale", 42, 42, "/status"))
        assert "دوطرفه" in out and "سلف‌بات" in out

    def test_status_bot_mode_unchanged(self, admin, pair):
        out = run(admin.handle("bale", 42, 42, "/status"))
        assert "mirbot" in out and "دوطرفه" not in out
