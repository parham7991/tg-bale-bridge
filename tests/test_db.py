"""تست‌های لایه ذخیره‌سازی."""
from tests.conftest import run  # noqa: F401


class TestPairs:
    def test_crud(self, db):
        pid = db.add_pair(-100111, "تی‌جی", "tgch", "777", "بله", "balech", "both")
        assert db.get_pair(pid)["mode"] == "both"
        assert db.list_pairs()[0]["id"] == pid
        assert db.set_mode(pid, "tg2bale")
        assert db.get_pair(pid)["mode"] == "tg2bale"
        assert db.remove_pair(pid)
        assert not db.get_pair(pid)

    def test_lookup_by_mode(self, db):
        pid = db.add_pair(-100111, "", "", "777", "", "", "tg2bale")
        assert db.pairs_for_tg(-100111)
        assert not db.pairs_for_bale("777")  # حالت tg2bale ⇒ از بله چیزی نمی‌آید
        db.set_mode(pid, "both")
        assert db.pairs_for_bale("777")
        assert not db.pairs_for_tg(-200222)

    def test_lookup_bale_by_username(self, db):
        db.add_pair(-1, "", "", "777", "", "balech", "both")
        assert db.pairs_for_bale("0", "BaleCh")  # بدون حساسیت به حروف
        assert not db.pairs_for_bale("0", "other")


class TestMessageMap:
    def test_roundtrip(self, db, pair):
        db.add_map(pair, "tg", "-100111", 10, "bale", "777", 55)
        o = db.other_side("tg", "-100111", 10, pair)
        assert o[0]["platform"] == "bale" and o[0]["msg"] == 55
        o2 = db.other_side("bale", "777", 55, pair)
        assert o2[0]["platform"] == "tg" and o2[0]["msg"] == 10

    def test_pair_isolation(self, db, pair):
        other = db.add_pair(-1, "", "", "888", "", "", "both")
        db.add_map(pair, "tg", "-100111", 10, "bale", "777", 55)
        assert not db.other_side("tg", "-100111", 10, other)

    def test_remove_and_replace(self, db, pair):
        db.add_map(pair, "tg", "-100111", 10, "bale", "777", 55)
        row = db.other_side("tg", "-100111", 10, pair)[0]
        db.replace_map_dst(row["row_id"], "bale", "777", 66)
        assert db.other_side("tg", "-100111", 10, pair)[0]["msg"] == 66
        db.remove_map_row(row["row_id"])
        assert not db.other_side("tg", "-100111", 10, pair)

    def test_album_many_to_many(self, db, pair):
        for i, j in zip((1, 2, 3), (51, 52, 53)):
            db.add_map(pair, "tg", "-100111", i, "bale", "777", j)
        assert len(db.other_side("tg", "-100111", 2, pair)) == 1
        assert db.other_side("bale", "777", 53, pair)[0]["msg"] == 3


class TestCaches:
    def test_sent_is_consumed_once(self, db):
        db.mark_sent("tg", "c", 5)
        assert db.was_sent("tg", "c", 5)
        assert not db.was_sent("tg", "c", 5)

    def test_fp_window(self, db):
        db.add_fp("bale", "c", "fp1")
        assert db.check_fp("bale", "c", "fp1", window=60)
        assert not db.check_fp("bale", "c", "fp1", window=60)

    def test_fp_expiry(self, db):
        import time
        db.add_fp("bale", "c", "fp2")
        db._conn.execute("UPDATE sent_fp SET created_at=? WHERE fp='fp2'", (time.time() - 120,))
        db._conn.commit()
        assert not db.check_fp("bale", "c", "fp2", window=60)

    def test_meta(self, db):
        assert db.get_meta("missing") is None
        db.set_meta("k", "v")
        assert db.get_meta("k") == "v"
        db.set_meta("k", "v2")
        assert db.get_meta("k") == "v2"
