"""ذخیره‌سازی وضعیت: جفت‌های کانال، نگاشت پیام‌ها و جلوگیری از حلقه."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_chat_id    INTEGER NOT NULL,
    tg_label      TEXT DEFAULT '',
    tg_username   TEXT DEFAULT '',
    bale_chat_id  TEXT NOT NULL,
    bale_label    TEXT DEFAULT '',
    bale_username TEXT DEFAULT '',
    mode          TEXT NOT NULL DEFAULT 'both',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS msg_map (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id     INTEGER NOT NULL,
    src_platform TEXT NOT NULL, src_chat TEXT NOT NULL, src_msg INTEGER NOT NULL,
    dst_platform TEXT NOT NULL, dst_chat TEXT NOT NULL, dst_msg INTEGER NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_map_src ON msg_map (src_platform, src_chat, src_msg);
CREATE INDEX IF NOT EXISTS idx_map_dst ON msg_map (dst_platform, dst_chat, dst_msg);

CREATE TABLE IF NOT EXISTS sent (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    chat       TEXT NOT NULL,
    msg        INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent ON sent (platform, chat, msg);

CREATE TABLE IF NOT EXISTS sent_fp (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    chat       TEXT NOT NULL,
    fp         TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fp ON sent_fp (platform, chat, fp);

CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

VALID_MODES = ("tg2bale", "bale2tg", "both")


class DB:
    def __init__(self, path: str | Path):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        self.prune_caches()

    # ---------- متا ----------
    def get_meta(self, k: str, default: str | None = None):
        with self._lock:
            row = self._conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row["v"] if row else default

    def set_meta(self, k: str, v: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (k, v),
            )
            self._conn.commit()

    # ---------- جفت‌ها ----------
    def add_pair(self, tg_chat_id, tg_label, tg_username, bale_chat_id, bale_label,
                 bale_username, mode) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO pairs(tg_chat_id, tg_label, tg_username,
                                     bale_chat_id, bale_label, bale_username, mode)
                   VALUES(?,?,?,?,?,?,?)""",
                (int(tg_chat_id), tg_label or "", tg_username or "",
                 str(bale_chat_id), bale_label or "", bale_username or "", mode),
            )
            self._conn.commit()
            return cur.lastrowid

    def remove_pair(self, pair_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM pairs WHERE id=?", (pair_id,))
            self._conn.execute("DELETE FROM msg_map WHERE pair_id=?", (pair_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def list_pairs(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM pairs ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_pair(self, pair_id: int):
        with self._lock:
            row = self._conn.execute("SELECT * FROM pairs WHERE id=?", (pair_id,)).fetchone()
        return dict(row) if row else None

    def set_mode(self, pair_id: int, mode: str) -> bool:
        with self._lock:
            cur = self._conn.execute("UPDATE pairs SET mode=? WHERE id=?", (mode, pair_id))
            self._conn.commit()
            return cur.rowcount > 0

    def pairs_for_tg(self, tg_chat_id):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pairs WHERE tg_chat_id=? AND mode IN ('tg2bale','both')",
                (int(tg_chat_id),),
            ).fetchall()
        return [dict(r) for r in rows]

    def pairs_for_bale(self, bale_chat_id, bale_username: str | None = None):
        q = "SELECT * FROM pairs WHERE (bale_chat_id=?"
        args = [str(bale_chat_id)]
        if bale_username:
            q += " OR (bale_username<>'' AND lower(bale_username)=lower(?))"
            args.append(bale_username.lstrip("@"))
        q += ") AND mode IN ('bale2tg','both')"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    # ---------- نگاشت پیام ----------
    def add_map(self, pair_id, src_platform, src_chat, src_msg,
                dst_platform, dst_chat, dst_msg):
        with self._lock:
            self._conn.execute(
                """INSERT INTO msg_map(pair_id, src_platform, src_chat, src_msg,
                                       dst_platform, dst_chat, dst_msg)
                   VALUES(?,?,?,?,?,?,?)""",
                (pair_id, src_platform, str(src_chat), int(src_msg),
                 dst_platform, str(dst_chat), int(dst_msg)),
            )
            self._conn.commit()

    def other_side(self, platform, chat, msg, pair_id=None):
        """پیام(های) معادل در سمت مقابل را برمی‌گرداند."""
        chat = str(chat)
        q = """SELECT * FROM msg_map
               WHERE ((src_platform=? AND src_chat=? AND src_msg=?)
                  OR (dst_platform=? AND dst_chat=? AND dst_msg=?))"""
        args = [platform, chat, int(msg), platform, chat, int(msg)]
        if pair_id is not None:
            q += " AND pair_id=?"
            args.append(pair_id)
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        out, seen = [], set()
        for r in rows:
            r = dict(r)
            if r["src_platform"] == platform and r["src_chat"] == chat and r["src_msg"] == int(msg):
                key = (r["dst_platform"], r["dst_chat"], r["dst_msg"], r["pair_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"platform": r["dst_platform"], "chat": r["dst_chat"],
                            "msg": r["dst_msg"], "pair_id": r["pair_id"], "row_id": r["id"]})
            else:
                key = (r["src_platform"], r["src_chat"], r["src_msg"], r["pair_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"platform": r["src_platform"], "chat": r["src_chat"],
                            "msg": r["src_msg"], "pair_id": r["pair_id"], "row_id": r["id"]})
        return out

    def remove_map_row(self, row_id: int):
        with self._lock:
            self._conn.execute("DELETE FROM msg_map WHERE id=?", (row_id,))
            self._conn.commit()

    def replace_map_dst(self, row_id, new_platform, new_chat, new_msg):
        """بعد از حذف+ارسال مجدد (ویرایش رسانه) نگاشت را به‌روز می‌کند."""
        with self._lock:
            self._conn.execute(
                "UPDATE msg_map SET dst_platform=?, dst_chat=?, dst_msg=? WHERE id=?",
                (new_platform, str(new_chat), int(new_msg), row_id),
            )
            self._conn.commit()

    # ---------- جلوگیری از حلقه ----------
    def mark_sent(self, platform, chat, msg):
        with self._lock:
            self._conn.execute(
                "INSERT INTO sent(platform, chat, msg, created_at) VALUES(?,?,?,?)",
                (platform, str(chat), int(msg), time.time()),
            )
            self._conn.commit()

    def was_sent(self, platform, chat, msg) -> bool:
        """اگر پیام توسط خود پل ساخته شده True و رد آن پاک می‌شود."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM sent WHERE platform=? AND chat=? AND msg=?",
                (platform, str(chat), int(msg)),
            ).fetchone()
            if row:
                self._conn.execute("DELETE FROM sent WHERE id=?", (row["id"],))
                self._conn.commit()
                return True
        return False

    def add_fp(self, platform, chat, fp):
        with self._lock:
            self._conn.execute(
                "INSERT INTO sent_fp(platform, chat, fp, created_at) VALUES(?,?,?,?)",
                (platform, str(chat), fp, time.time()),
            )
            self._conn.commit()

    def check_fp(self, platform, chat, fp, window: float = 60.0) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM sent_fp WHERE platform=? AND chat=? AND fp=? AND created_at>?",
                (platform, str(chat), fp, time.time() - window),
            ).fetchone()
            if row:
                self._conn.execute("DELETE FROM sent_fp WHERE id=?", (row["id"],))
                self._conn.commit()
                return True
        return False

    def prune_caches(self, max_age: float = 2 * 24 * 3600):
        cutoff = time.time() - max_age
        with self._lock:
            self._conn.execute("DELETE FROM sent WHERE created_at<?", (cutoff,))
            self._conn.execute("DELETE FROM sent_fp WHERE created_at<?", (cutoff,))
            self._conn.commit()
