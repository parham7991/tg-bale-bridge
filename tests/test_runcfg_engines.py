"""تست‌های بستهٔ نگارخانهٔ تنظیمات (bridge/runcfg) — موتورهای KV/اکانت‌ها/آمادگی."""
from __future__ import annotations

from types import SimpleNamespace

from bridge.runcfg import Store
from bridge.runcfg.accounts import AccountsEngine
from bridge.runcfg.kvstore import JsonKVEngine
from bridge.runcfg.readiness import ReadinessEngine
from bridge.runcfg.types_map import PREFIX, admin_id_from, key_of
from tests.conftest import run  # noqa: F401 — هماهنگی با بقیهٔ تست‌ها


class FakeDB:
    def __init__(self):
        self.meta = {}

    def get_meta(self, k, default=None):
        return self.meta.get(k, default)

    def set_meta(self, k, v):
        self.meta[k] = v


# ───────────────────────────── types_map ─────────────────────────────

def test_key_prefix_and_admin_extractor():
    assert PREFIX == "cfg:" and key_of("x") == "cfg:x"
    assert admin_id_from({"id": 5, "username": "u"}) == 5
    assert admin_id_from(7) == 7
    assert admin_id_from(None) == 0
    assert admin_id_from({"id": None}) == 0


# ───────────────────────────── JsonKVEngine ─────────────────────────────

def test_json_roundtrip_persian_and_defaults():
    kv = JsonKVEngine(FakeDB())
    kv.set("تنظیم", {"متن": "فارسی", "n": 3})
    assert kv.get("تنظیم") == {"متن": "فارسی", "n": 3}
    assert kv.get("غایب") is None
    assert kv.get("غایب", 42) == 42
    # مقدار خراب → پیش‌فرض
    db = FakeDB()
    db.set_meta("cfg:bad", "{نه جیسون")
    assert JsonKVEngine(db).get("bad", "پیش‌فرض") == "پیش‌فرض"


def test_json_delete_softens():
    kv = JsonKVEngine(FakeDB())
    kv.set("k", [1, 2])
    kv.delete("k")
    assert kv.get("k", "پاک‌شده") == "پاک‌شده"


# ───────────────────────────── AccountsEngine ─────────────────────────────

def test_claim_admin_first_only():
    acc = AccountsEngine(JsonKVEngine(FakeDB()))
    assert acc.admin_tg_id() == 0
    assert acc.claim_admin(555, "parham") is True
    assert acc.admin_tg_id() == 555
    assert acc.claim_admin(666, "other") is False
    assert acc.admin_tg_id() == 555


def test_account_setters_shape():
    acc = AccountsEngine(JsonKVEngine(FakeDB()))
    acc.set_tg_api("123", "hash")           # api_id رشته هم int می‌شود
    acc.set_tg_self("+98910")
    acc.set_bale_self("+98912")
    acc.set_bale_bot("42:TOK", {"username": "bb"})
    assert acc.tg_api() == {"api_id": 123, "api_hash": "hash"}
    assert acc.tg_self() == {"phone": "+98910"}
    assert acc.bale_self() == {"phone": "+98912"}
    assert acc.bale_bot() == {"token": "42:TOK", "me": {"username": "bb"}}


# ───────────────────────────── ReadinessEngine ─────────────────────────────

def test_readiness_tg_needs_session_file(tmp_path):
    acc = AccountsEngine(JsonKVEngine(FakeDB()))
    rd = ReadinessEngine(acc)
    cfg = SimpleNamespace(TG_API_ID=1, TG_API_HASH="h", SESSION_PATH=tmp_path / "tg")
    assert not rd.has_tg(cfg)                       # نشست نیست
    (tmp_path / "tg.session").write_text("x")
    assert rd.has_tg(cfg)                           # حالا هست
    # از store هم می‌آید (env خالی)
    cfg2 = SimpleNamespace(TG_API_ID=0, TG_API_HASH="", SESSION_PATH=tmp_path / "tg")
    acc.set_tg_api(9, "h2")
    assert rd.has_tg(cfg2)


def test_readiness_bale_paths(tmp_path):
    acc = AccountsEngine(JsonKVEngine(FakeDB()))
    rd = ReadinessEngine(acc)
    cfg = SimpleNamespace(BALE_TOKEN="", BALE_MODE="bot", BALE_SESSION=str(tmp_path / "s"))
    assert not rd.has_bale(cfg)
    acc.set_bale_self("+98912")                     # سلف ثبت شد
    assert rd.has_bale(cfg)
    # حالت ربات با توکن env
    acc2 = AccountsEngine(JsonKVEngine(FakeDB()))
    rd2 = ReadinessEngine(acc2)
    cfg2 = SimpleNamespace(BALE_TOKEN="x:T", BALE_MODE="bot", BALE_SESSION="")
    assert rd2.has_bale(cfg2)
    # حالت سلف با فایل نشست واقعی .bale
    acc3 = AccountsEngine(JsonKVEngine(FakeDB()))
    rd3 = ReadinessEngine(acc3)
    sess = tmp_path / "sess.bale"
    sess.write_text("x")
    cfg3 = SimpleNamespace(BALE_TOKEN="", BALE_MODE="user", BALE_SESSION=str(sess))
    assert rd3.has_bale(cfg3)
    # installed = هر دو سو
    cfg4 = SimpleNamespace(TG_API_ID=1, TG_API_HASH="h", SESSION_PATH=tmp_path / "tg",
                           BALE_TOKEN="x:T", BALE_MODE="bot", BALE_SESSION="")
    (tmp_path / "tg.session").write_text("x")
    assert rd3.installed(cfg4) is True


# ───────────────────────────── نما (Store) ─────────────────────────────

def test_facade_full_surface():
    st = Store(FakeDB())
    st.set("x", {"a": 1})
    assert st.get("x") == {"a": 1}
    st.delete("x")
    assert st.claim_admin(1, "u")
    st.set_bale_bot("t", {"username": "b"})
    assert st.bale_bot()["me"]["username"] == "b"
    # سمت بله آماده (توکن ربات) اما تلگرام نه (نشست ندارد) → نصب ناقص
    assert not st.installed(SimpleNamespace(
        TG_API_ID=0, TG_API_HASH="", SESSION_PATH="",
        BALE_TOKEN="t", BALE_MODE="bot", BALE_SESSION=""))
