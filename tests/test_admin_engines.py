"""تست‌های بستهٔ پنل ادمین (bridge/admin) — موتورهای پارس/سطوح/resolve/دستورات."""
from __future__ import annotations

from types import SimpleNamespace

from bridge.admin import (
    CMD_ALIASES,
    HELP,
    MINIMAL_HELP,
    MODE_ALIASES,
    Admin,
)
from bridge.admin.resolver import ResolverEngine
from bridge.admin.surfaces import SurfacesEngine
from bridge.admin.types_map import fmt_duration, parse_command, parse_pair_id
from tests.conftest import run

# ───────────────────────────── فیک‌ها ─────────────────────────────

class FakeBridge:
    def __init__(self):
        self.paused = False
        self.bale_bot = {"id": 42, "username": "mirbot"}

    async def b2t_entity(self, chat_id):
        return f"ent:{chat_id}"


def make_admin(cfg=None, bale=None, tg=None, db=None, log_buffer=None):
    cfg = cfg or SimpleNamespace(ADMIN_BALE_ID=42, BALE_MODE="bot", BALE_TOKEN="",
                                 DASH_ENABLED=False)
    bridge = FakeBridge()
    db = db or SimpleNamespace(
        stats=lambda: {"pairs": 2, "mapped": 10},
        list_pairs=lambda: [], get_pair=lambda pid: None,
        set_meta=lambda *a: None, mark_sent=lambda *a: None)
    adm = Admin(db, bale, tg, bridge, cfg, log_buffer=log_buffer, started_at=1000.0)
    return adm, cfg


# ───────────────────────────── پارس و نگاشت‌ها ─────────────────────────────

def test_parse_command_slash_and_aliases():
    assert parse_command("/add @a @b both") == ("add", ["@a", "@b", "both"])
    assert parse_command("/start@my_bot")[0] == "help"
    assert parse_command("لیست")[0] == "list"
    assert parse_command("hello") == (None, [])
    assert parse_command("") == (None, [])


def test_mode_aliases_complete():
    assert MODE_ALIASES["دو طرفه"] == "both" and MODE_ALIASES["b2t"] == "bale2tg"


def test_fmt_duration():
    assert fmt_duration(0) == "0m"
    assert fmt_duration(3660) == "1h 1m"
    assert fmt_duration(90000) == "1d 1h 0m"


def test_help_texts_present():
    assert "/add" in HELP and "/add" in MINIMAL_HELP


# ───────────────────────────── SurfacesEngine ─────────────────────────────

def test_surfaces_bot_mode():
    s = SurfacesEngine(SimpleNamespace(BALE_MODE="bot", BALE_TOKEN=""))
    assert not s.is_user_mode()
    assert s.surfaces({}) == "ربات بله + Saved Messages تلگرام"
    assert s.bale_mode_label() == "ربات بله"


def test_surfaces_user_mode_with_token():
    s = SurfacesEngine(SimpleNamespace(BALE_MODE="user", BALE_TOKEN="tok"))
    assert s.surfaces({}) == ("خودچت بله (پیام به خودتان) + ربات بله"
                              " + Saved Messages تلگرام")
    assert s.surfaces({"username": "ctrl"}) == (
        "خودچت بله (پیام به خودتان) + ربات بله + بات تلگرام + Saved Messages تلگرام")


# ───────────────────────────── ResolverEngine ─────────────────────────────

def test_resolve_tg_success_and_error(monkeypatch):
    class FakeTg:
        async def get_entity(self, ref):
            if ref == "@ok":
                return SimpleNamespace(id=123, title="کانال", username="ok",
                                       first_name=None, last_name=None)
            raise RuntimeError("nope")

    monkeypatch.setattr("bridge.admin.resolver.tg_utils.get_peer_id",
                        lambda ent: -1000000000123)
    r = ResolverEngine(SimpleNamespace(tg=FakeTg()))
    mid, label, uname = run(r.resolve_tg("@ok"))
    assert mid == -1000000000123 and label == "کانال" and uname == "ok"
    try:
        run(r.resolve_tg("@nope"))
        assert False
    except ValueError as e:
        assert "پیدا نشد" in str(e) and "/id" in str(e)


def test_describe_forward_bale_shape():
    r = ResolverEngine(SimpleNamespace(tg=None))
    out = run(r.describe_forward("bale", {
        "forward_from_chat": {"id": 55, "title": "کانال خصوصی"}}))
    assert "55" in out and "کانال خصوصی" in out


def test_describe_forward_none():
    r = ResolverEngine(SimpleNamespace(tg=None))
    assert run(r.describe_forward("bale", {})) is None
    assert run(r.describe_forward("bale", None)) is None


# ───────────────────────────── facade: احراز و dispatch ─────────────────────────────

def test_bale_bootstrap_and_rejection():
    # bootstrap: ADMIN_BALE_ID=0 → پیام راهنمای آیدی برای هر کسی
    adm, _ = make_admin(cfg=SimpleNamespace(ADMIN_BALE_ID=0, BALE_MODE="bot"))
    out = run(adm.handle("bale", 123, 123, "/start"))
    assert "123" in out and "ADMIN_BALE_ID" in out
    # rejection: ادمین تعیین شده → غیرادمین None می‌گیرد
    adm2, _ = make_admin()          # ADMIN_BALE_ID=42
    assert run(adm2.handle("bale", 1, 999, "/list")) is None


def test_unknown_command_and_minimal_help():
    adm, _ = make_admin()
    assert "ناشناخته" in run(adm.handle("bale", 1, 42, "/whatever"))
    assert "پل" in run(adm.handle("bale", 1, 42, "سلام چی کار کنم؟"))
    assert run(adm.handle("bale", 1, 42, "/help")) == HELP


def test_current_user_id_surfaces_in_whoami():
    adm, cfg = make_admin(cfg=SimpleNamespace(
        ADMIN_BALE_ID=42, BALE_MODE="user", BALE_TOKEN="x",
        DASH_ENABLED=False))

    class FakeTg:
        async def get_me(self):
            return SimpleNamespace(username="selfuser", first_name="پرهام", id=7)

    adm.tg = FakeTg()
    out = run(adm.handle("bale", 1, 42, "/whoami"))
    assert "42" in out and "selfuser" in out and "خودچت" in out


def test_engine_reads_live_attrs_from_facade():
    adm, _ = make_admin(log_buffer=None)
    assert adm.system_cmd.log_buffer is None        # زنده
    buf = SimpleNamespace(tail=lambda n: ["l1"])
    adm.log_buffer = buf                            # پچ بعد از ساخت
    assert adm.system_cmd.log_buffer is buf
    out = run(adm.handle("bale", 1, 42, "/logs 1"))
    assert "l1" in out


# ───────────────────────────── کنترل و جفت‌ها ─────────────────────────────

def test_pause_resume_roundtrip():
    calls = []
    db = SimpleNamespace(stats=lambda: {"pairs": 0, "mapped": 0},
                         list_pairs=lambda: [], get_pair=lambda pid: None,
                         set_meta=lambda k, v: calls.append((k, v)),
                         mark_sent=lambda *a: None)
    adm, _ = make_admin(db=db)
    assert "⏸" in run(adm.handle("bale", 1, 42, "/pause"))
    assert adm.bridge.paused is True and calls[-1] == ("paused", "1")
    assert "▶️" in run(adm.handle("bale", 1, 42, "/resume"))
    assert adm.bridge.paused is False and calls[-1] == ("paused", "0")


def test_pairs_list_empty_and_cmd_remove_format():
    adm, _ = make_admin()
    assert "جفتی ثبت نشده" in run(adm.handle("bale", 1, 42, "/list"))
    assert "فرمت" in run(adm.handle("bale", 1, 42, "/remove"))


def test_cmd_setup_hint():
    adm, _ = make_admin()
    out = run(adm.handle("bale", 1, 42, "/setup"))
    assert "بات مدیریت تلگرام" in out


def test_alias_surface_full_coverage():
    # هر دستور HELP باید در CMD_ALIASES هم باشد (بدون نمونه‌های عددی)
    for token in ("add", "list", "mode", "remove", "test", "status", "id", "whoami",
                  "pause", "resume", "logs", "access", "promote", "dashboard",
                  "passwd", "dashuser", "setup"):
        assert token in CMD_ALIASES, token

# ───────────────── شناسهٔ جفت: «#1» و ارقام فارسی (رگرسیون v2.17.5) ─────────────────

def test_parse_pair_id_shapes():
    assert parse_pair_id("#1") == 1
    assert parse_pair_id(" 1 ") == 1
    assert parse_pair_id("۲") == 2          # ارقام فارسی
    assert parse_pair_id("№3") == 3
    assert parse_pair_id(4) == 4
    assert parse_pair_id("abc") is None
    assert parse_pair_id("#x") is None
    assert parse_pair_id("0") is None
    assert parse_pair_id("-2") is None
    assert parse_pair_id("") is None
    assert parse_pair_id(None) is None


def test_cmd_test_accepts_hash_pair_id():
    sent = []

    async def fake_send(cid, text):
        sent.append((cid, text))

    bale = SimpleNamespace(send_message=fake_send)
    pair = {"id": 1, "mode": "tg2bale", "bale_chat_id": 55, "tg_chat_id": 66}
    db = SimpleNamespace(get_pair=lambda pid: pair if pid == 1 else None,
                         set_meta=lambda *a: None, mark_sent=lambda *a: None)
    adm, _ = make_admin(bale=bale, db=db)
    out = run(adm.handle("tg", 1, 42, "/test #1"))
    assert sent and sent[0][0] == 55
    assert "بله ✔" in out


def test_cmd_test_invalid_pair_id_format_hint():
    adm, _ = make_admin(db=SimpleNamespace(get_pair=lambda pid: None))
    out = run(adm.handle("tg", 1, 42, "/test abc"))
    assert "فرمت" in out


def test_cmd_mode_accepts_hash_pair_id():
    calls = []
    db = SimpleNamespace(set_mode=lambda pid, mode: calls.append((pid, mode)) or True)
    adm, _ = make_admin(db=db)
    out = run(adm.handle("tg", 1, 42, "/mode #1 both"))
    assert calls == [(1, "both")]
    assert "جهت جفت #1" in out


def test_cmd_mode_invalid_id_format_hint():
    adm, _ = make_admin()
    assert "فرمت" in run(adm.handle("tg", 1, 42, "/mode x both"))


def test_cmd_remove_accepts_hash_pair_id():
    calls = []
    db = SimpleNamespace(remove_pair=lambda pid: calls.append(pid) or True)
    adm, _ = make_admin(db=db)
    out = run(adm.handle("tg", 1, 42, "/remove #2"))
    assert calls == [2]
    assert "حذف شد" in out
    assert "فرمت" in run(adm.handle("tg", 1, 42, "/remove q"))
