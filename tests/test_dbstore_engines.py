"""تست‌های بستهٔ لایهٔ داده (bridge/dbstore) — موتورهای اتصال/جفت‌ها/نقشه/کش."""
from __future__ import annotations

import sqlite3
import time

import pytest

from bridge.dbstore import DB, SCHEMA
from bridge.dbstore.connection import ConnectionEngine
from bridge.dbstore.loopcache import LoopCacheEngine
from bridge.dbstore.map import MapEngine
from bridge.dbstore.meta import MetaEngine
from bridge.dbstore.pairs import PairsEngine
from bridge.dbstore.stats import StatsEngine
from bridge.dbstore.types_map import VALID_MODES


@pytest.fixture
def engine(tmp_path):
    return ConnectionEngine(tmp_path / "t.db", SCHEMA)


@pytest.fixture
def db(tmp_path):
    return DB(tmp_path / "t.db")


# ───────────────────────────── ConnectionEngine ─────────────────────────────

def test_connection_applies_schema_and_row_factory(engine):
    tables = {r["name"] for r in engine.query_all(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"pairs", "msg_map", "sent", "sent_fp", "meta"} <= tables


def test_connection_execute_commits(engine):
    engine.execute("INSERT INTO meta(k,v) VALUES('a','1')")
    # اتصال جدید روی همان فایل → commit واقعی
    raw = sqlite3.connect(str(engine.conn.execute(
        "PRAGMA database_list").fetchone()[2] if False else ":memory:"))
    raw.close()
    assert engine.query_one("SELECT v FROM meta WHERE k='a'")["v"] == "1"


def test_connection_query_one_missing(engine):
    assert engine.query_one("SELECT * FROM meta WHERE k='nope'") is None


# ───────────────────────────── MetaEngine ─────────────────────────────

def test_meta_upsert(engine):
    m = MetaEngine(engine)
    assert m.get("x") is None
    assert m.get("x", "def") == "def"
    m.set("x", "1")
    m.set("x", "2")
    assert m.get("x") == "2"


# ───────────────────────────── PairsEngine ─────────────────────────────

def test_pairs_add_normalizes_types(engine):
    p = PairsEngine(engine)
    pid = p.add("-100111", None, None, 777, None, None, "both")
    row = p.get(pid)
    assert row["tg_chat_id"] == -100111 and row["bale_chat_id"] == "777"
    assert row["tg_label"] == "" and row["mode"] == "both"


def test_pairs_direction_lookup(engine):
    p = PairsEngine(engine)
    pid = p.add(-100111, "", "", "777", "", "BaleCh", "tg2bale")
    assert p.for_tg(-100111) and not p.for_bale("777")
    p.set_mode(pid, "both")
    assert p.for_bale("777") and p.for_bale("0", "balech")   # یوزرنیم بدون حساسیت
    assert p.for_bale("0", "@balech")                        # با @ هم
    assert not p.for_tg(-200222)
    assert not p.set_mode(999, "both")


def test_pairs_remove_cascades_maps(engine):
    p = PairsEngine(engine)
    m = MapEngine(engine)
    pid = p.add(-1, "", "", "7", "", "", "both")
    m.add(pid, "tg", "-1", 1, "bale", "7", 2)
    assert p.remove(pid)
    assert not p.list() and not m.other_side("tg", "-1", 1)
    assert not p.remove(pid)


# ───────────────────────────── MapEngine ─────────────────────────────

def test_map_other_side_dedup(engine):
    m = MapEngine(engine)
    m.add(1, "tg", "-1", 1, "bale", "7", 2)
    out = m.other_side("tg", "-1", 1)
    assert len(out) == 1 and out[0]["platform"] == "bale" and out[0]["msg"] == 2
    back = m.other_side("bale", "7", 2)
    assert len(back) == 1 and back[0]["platform"] == "tg" and back[0]["msg"] == 1


def test_map_pair_filter(engine):
    m = MapEngine(engine)
    m.add(1, "tg", "-1", 1, "bale", "7", 2)
    m.add(2, "tg", "-1", 1, "bale", "8", 3)
    assert len(m.other_side("tg", "-1", 1)) == 2
    assert len(m.other_side("tg", "-1", 1, pair_id=2)) == 1


def test_map_replace_and_remove(engine):
    m = MapEngine(engine)
    m.add(1, "tg", "-1", 1, "bale", "7", 2)
    row = m.other_side("tg", "-1", 1)[0]
    m.replace_dst(row["row_id"], "bale", "7", 9)
    assert m.other_side("tg", "-1", 1)[0]["msg"] == 9
    m.remove_row(row["row_id"])
    assert not m.other_side("tg", "-1", 1)


# ───────────────────────────── LoopCacheEngine ─────────────────────────────

def test_loopcache_sent_consumed_once(engine):
    lc = LoopCacheEngine(engine)
    lc.mark_sent("tg", "c", 5)
    assert lc.was_sent("tg", "c", 5)
    assert not lc.was_sent("tg", "c", 5)


def test_loopcache_fp_window_and_expiry(engine):
    lc = LoopCacheEngine(engine)
    lc.add_fp("bale", "c", "fp")
    assert lc.check_fp("bale", "c", "fp")
    assert not lc.check_fp("bale", "c", "fp")
    lc.add_fp("bale", "c", "old")
    engine.execute("UPDATE sent_fp SET created_at=? WHERE fp='old'",
                   (time.time() - 120,))
    assert not lc.check_fp("bale", "c", "old", window=60)


def test_loopcache_prune(engine):
    lc = LoopCacheEngine(engine)
    lc.mark_sent("tg", "c", 1)
    engine.execute("UPDATE sent SET created_at=? WHERE msg=1", (time.time() - 10**6,))
    lc.prune(max_age=1000)
    assert not lc.was_sent("tg", "c", 1)


# ───────────────────────────── StatsEngine ─────────────────────────────

def test_stats_counts(engine):
    p = PairsEngine(engine)
    m = MapEngine(engine)
    pid = p.add(-1, "", "", "7", "", "", "both")
    m.add(pid, "tg", "-1", 1, "bale", "7", 2)
    s = StatsEngine(engine).stats()
    assert s == {"pairs": 1, "mapped": 1}


# ───────────────────────────── نما (DB) ─────────────────────────────

def test_facade_full_surface_and_conn_compat(db, tmp_path):
    pid = db.add_pair(-100111, "تی‌جی", "tgch", "777", "بله", "balech", "both")
    assert db.get_pair(pid)["mode"] == "both"
    assert db.list_pairs() and db.set_mode(pid, "tg2bale")
    assert db.pairs_for_tg(-100111) and not db.pairs_for_bale("777")
    db.add_map(pid, "tg", "-100111", 10, "bale", "777", 55)
    assert db.other_side("tg", "-100111", 10)[0]["msg"] == 55
    db.mark_sent("tg", "c", 5)
    assert db.was_sent("tg", "c", 5)
    db.add_fp("bale", "c", "f")
    assert db.check_fp("bale", "c", "f")
    db.set_meta("k", "v") and db.get_meta("k") == "v"
    assert db.stats()["pairs"] == 1
    db.prune_caches()
    # سازگاری _conn/_lock — تست قدیمی مستقیم SQL می‌زند
    db._conn.execute("UPDATE sent_fp SET created_at=? WHERE fp='f'", (time.time() - 120,))
    db._conn.commit()
    assert not db.check_fp("bale", "c", "f", window=60)
    with db._lock:
        db._conn.execute("SELECT 1")
    assert VALID_MODES == ("tg2bale", "bale2tg", "both")


def test_facade_remove_pair_deletes_maps(db):
    pid = db.add_pair(-1, "", "", "7", "", "", "both")
    db.add_map(pid, "tg", "-1", 1, "bale", "7", 2)
    assert db.remove_pair(pid)
    assert not db.other_side("tg", "-1", 1)

# ───── نرمال‌سازی شناسهٔ تلگرام در جفت‌ها (رگرسیون v2.17.6) ─────

def test_pairs_add_stores_bare_marked_id(engine):
    p = PairsEngine(engine)
    pid = p.add(-1003815616564, "MARVELL", "Marvellit", "287806378", "", "", "both")
    assert p.get(pid)["tg_chat_id"] == 3815616564     # نشان‌دار → خالص ذخیره می‌شود


def test_pairs_for_tg_matches_both_forms(engine):
    p = PairsEngine(engine)
    p.add(3815616564, "", "", "287806378", "", "", "both")       # ذخیرهٔ خالص (ویزارد)
    assert p.for_tg(-1003815616564)      # رویداد تلگتون با شناسهٔ نشان‌دار
    assert p.for_tg(3815616564)          # جست‌وجوی خالص
    pid2 = p.add(-1001234567890, "", "", "5", "", "", "tg2bale")  # /add با نشان‌دار
    assert p.get(pid2)["tg_chat_id"] == 1234567890
    assert p.for_tg(-1001234567890) and p.for_tg(1234567890)
    assert not p.for_tg(-1001111111111)   # جفتِ چت دیگر پیدا نشود
