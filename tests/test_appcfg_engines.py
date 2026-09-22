"""تست‌های بستهٔ پیکربندی (bridge/appcfg) — آفلاین با env تزریقی."""
from __future__ import annotations

from pathlib import Path

import config
from bridge.appcfg import EnvParseEngine, PathsEngine, SectionsEngine, ValidatorEngine, populate

# ───────────────────────────── EnvParseEngine ─────────────────────────────

def test_envparse_int_float_flag():
    p = EnvParseEngine({"I": "7", "F": "0.5", "FLAG0": "0", "FLAGNO": "no",
                        "FLAGYES": "true", "BAD": "abc", "EMPTY": ""})
    assert p.int_of("I") == 7 and p.int_of("BAD") == 0 and p.int_of("EMPTY", 5) == 5
    assert p.float_of("F", 0.9) == 0.5 and p.float_of("BAD", 0.9) == 0.9
    assert p.flag("FLAG0") is False and p.flag("FLAGNO") is False
    assert p.flag("FLAGYES") is True and p.flag("MISSING") is True


# ───────────────────────────── SectionsEngine ─────────────────────────────

def test_sections_tg_and_control():
    sec = SectionsEngine({"TG_API_ID": "12", "TG_API_HASH": " h ", "TG_PHONE": "+98...",
                          "TG_BOT_TOKEN": "T:K", "TG_BOT_API_BASE": "https://x.org/",
                          "ADMIN_TG_ID": "777"})
    tg = sec.tg()
    assert tg["TG_API_ID"] == 12 and tg["TG_API_HASH"] == "h"
    ctl = sec.control()
    assert ctl["TG_BOT_API_BASE"] == "https://x.org" and ctl["ADMIN_TG_ID"] == 777


def test_sections_bale_defaults_and_env(tmp_path):
    sec = SectionsEngine({})
    b = sec.bale(tmp_path / "data")
    assert b["BALE_MODE"] == "bot" and b["BALE_TOKEN"] == ""
    assert b["BALE_API_BASE"] == "https://tapi.bale.ai"
    assert b["BALE_SESSION"] == str(tmp_path / "data" / "session")

    sec2 = SectionsEngine({"BALE_MODE": "USER", "BALE_TOKEN": " t ", "BALE_SESSION": "/s"})
    b2 = sec2.bale(tmp_path / "data")
    assert b2["BALE_MODE"] == "user" and b2["BALE_TOKEN"] == "t"
    assert b2["BALE_SESSION"] == "/s"          # env بر پیش‌فرض می‌چربد


def test_sections_general_and_dash():
    sec = SectionsEngine({"ALBUM_DELAY": "1.5", "BALE_POLL_TIMEOUT": "0",
                          "DASH_ENABLED": "0", "DASH_PORT": "0", "DASH_HOST": "127.0.0.1"})
    g = sec.general()
    d = sec.dash()
    assert g["ALBUM_DELAY"] == 1.5 and g["BALE_POLL_TIMEOUT"] == 30   # 0 → 30
    assert d["DASH_ENABLED"] is False and d["DASH_PORT"] == 8080      # 0 → 8080
    assert d["DASH_HOST"] == "127.0.0.1"
    assert SectionsEngine({}).dash()["DASH_ENABLED"] is True          # پیش‌فرض روشن


# ───────────────────────────── PathsEngine ─────────────────────────────

def test_paths_engine_creates_dirs(tmp_path):
    base = tmp_path / "repo"
    base.mkdir()
    pe = PathsEngine({"DATA_DIR": str(tmp_path / "dd")}, base_dir=base)
    paths = pe.build()
    assert paths["BASE_DIR"] == base
    assert paths["DATA_DIR"] == (tmp_path / "dd").resolve()
    assert (tmp_path / "dd" / "tmp").is_dir()
    assert paths["DB_PATH"].name == "bridge.db" and paths["SESSION_PATH"].name == "tg"


# ───────────────────────────── ValidatorEngine ─────────────────────────────

def test_validator_all_branches(tmp_path):
    v = ValidatorEngine()
    # همه‌چیز ناموجود → دو مشکل (اعتبارنامهٔ TG + توکن بله؛ حالت bot معتبر است)
    p = v.run({"TG_API_ID": 0, "TG_API_HASH": "", "BALE_MODE": "bot",
               "BALE_TOKEN": "", "BALE_SESSION": ""})
    assert len(p) == 2
    # حالت نامعتبر
    p = v.run({"TG_API_ID": 1, "TG_API_HASH": "h", "BALE_MODE": "x",
               "BALE_TOKEN": "t", "BALE_SESSION": ""})
    assert any("BALE_MODE" in s for s in p)
    # user بدون نشست
    sess = str(tmp_path / "sess")
    p = v.run({"TG_API_ID": 1, "TG_API_HASH": "h", "BALE_MODE": "user",
               "BALE_TOKEN": "", "BALE_SESSION": sess})
    assert any("login_bale" in s for s in p)
    # user با نشست .bale موجود → سالم
    ok_sess = tmp_path / "sess.bale"
    ok_sess.write_text("x")
    p = v.run({"TG_API_ID": 1, "TG_API_HASH": "h", "BALE_MODE": "user",
               "BALE_TOKEN": "", "BALE_SESSION": str(ok_sess)})
    assert p == []


# ───────────────────────────── populate + شیم زنده ─────────────────────────────

def test_populate_injects_and_validate_is_live(tmp_path):
    ns: dict = {}
    populate(ns, env={"TG_API_ID": "1", "TG_API_HASH": "h", "BALE_MODE": "bot",
                      "BALE_TOKEN": "t", "DATA_DIR": str(tmp_path / "dd")})
    assert ns["LIMIT_TEXT"] == 4096 and callable(ns["validate"])
    assert ns["BALE_POLL_TIMEOUT"] == 30
    assert ns["validate"]() == []
    ns["BALE_MODE"] = "bogus"                     # mutation باید دیده شود
    assert any("BALE_MODE" in s for s in ns["validate"]())
    ns["BALE_MODE"] = "bot"
    assert ns["validate"]() == []


def test_config_shim_module_surface(monkeypatch):
    assert config.LIMIT_CAPTION_GROUP == 1024
    assert callable(config.validate)
    assert config.BASE_DIR == Path(config.__file__).resolve().parent
    assert str(config.DATA_DIR)                   # مسیر واقعی ساخته شده
    # mutation روی ماژول → validate زنده همان را می‌بیند (مثل OverridesEngine)
    monkeypatch.setattr(config, "BALE_MODE", "x")
    assert any("BALE_MODE" in s for s in config.validate())
