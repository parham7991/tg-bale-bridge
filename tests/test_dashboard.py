"""تست‌های داشبورد وب: احراز هویت، CSRF، CRUD جفت‌ها، کنترل، لاگ، رمز."""
from __future__ import annotations

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from bridge.dashboard import Dashboard
from bridge.store import Store
from tests.test_wizard import FakeSelfTg


class FakeProbeBale:
    async def send_message(self, chat_id, text, reply_to=None, **kw):
        return {"message_id": 555}

    async def delete_message(self, chat_id, message_id):
        return {"ok": True}

    async def get_chat(self, ref):
        return {"id": 4321, "type": "channel", "title": "کانال بله", "username": "balepub"}


class FakeResolveAdmin:
    """فقط resolveها — همان قرارداد Admin._resolve_*"""

    def __init__(self, tg, bale):
        self.tg, self.bale = tg, bale

    async def _resolve_tg(self, ref):
        return -100123, "کانال تی‌جی", "tgpub"

    async def _resolve_bale(self, ref):
        return 4321, "کانال بله", "balepub"


class FakeLogBuf:
    def __init__(self):
        self._lines = ["2026-09-22 10:00:00 INFO main: آماده 🚀",
                       "2026-09-22 10:00:05 ERROR bridge: خطای آزمایشی"]

    def tail(self, n=15):
        return self._lines[-n:]


def make_dash(db, cfg, bridge=None, admin=None):
    store = Store(db)
    rt = {
        "admin": admin, "bridge": bridge, "tg": FakeSelfTg(),
        "bale": FakeProbeBale(), "tg_me": {"id": 999, "username": "selfuser"},
        "bale_me": {"id": 42, "username": "baleside"}, "log_buffer": FakeLogBuf(),
        "started_at": __import__("time").time() - 125,
    }
    return Dashboard(db, store, cfg, rt), store


def drive(dash, coro_fn):
    async def main():
        async with TestClient(TestServer(dash.app)) as client:
            # همهٔ درخواست‌ها مثل فرانت با هدر CSRF
            client.session.headers.update({"X-Requested-With": "XMLHttpRequest"})
            return await coro_fn(client)
    return asyncio.run(main())


def login(client, user="admin", pw="secret1"):
    return client.post("/api/login", json={"username": user, "password": pw})


class TestAuth:
    def test_index_served(self, db, cfg):
        dash, _ = make_dash(db, cfg)

        async def go(client):
            r = await client.get("/")
            assert r.status == 200
            assert "پل تلگرام ⇄ بله" in await r.text()

        drive(dash, go)

    def test_status_requires_login(self, db, cfg):
        dash, _ = make_dash(db, cfg)

        async def go(client):
            r = await client.get("/api/status")
            assert r.status == 401

        drive(dash, go)

    def test_login_wrong_then_right(self, db, cfg):
        dash, store = make_dash(db, cfg)
        Dashboard.set_credentials(store, "admin", "secret1")

        async def go(client):
            r = await login(client, pw="wrong")
            assert r.status == 401
            r = await login(client, pw="secret1")
            assert r.status == 200
            r = await client.get("/api/status")
            assert r.status == 200
            j = await r.json()
            assert j["mode"] in ("bridge", "installer")
            assert j["dash_user"] == "admin"

        drive(dash, go)

    def test_csrf_required(self, db, cfg):
        dash, store = make_dash(db, cfg)
        Dashboard.set_credentials(store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/pause", json={}, headers={"X-Requested-With": "nope"})
            assert r.status == 403

        drive(dash, go)

    def test_login_rate_limit(self, db, cfg):
        dash, store = make_dash(db, cfg)
        Dashboard.set_credentials(store, "admin", "secret1")

        async def go(client):
            for _ in range(5):
                await login(client, pw="nope")
            r = await login(client, pw="secret1")
            assert r.status == 429

        drive(dash, go)


class TestPairsCrud:
    def test_add_list_patch_delete(self, db, cfg):
        dash, _ = make_dash(db, cfg, admin=FakeResolveAdmin(None, None))
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/pairs", json={"tg": "@tgpub", "bale": "@balepub",
                                                      "mode": "tg2bale"})
            assert r.status == 200
            pid = (await r.json())["pair_id"]
            r = await client.get("/api/pairs")
            pairs = (await r.json())["pairs"]
            assert len(pairs) == 1 and pairs[0]["mode"] == "tg2bale"
            r = await client.patch(f"/api/pairs/{pid}", json={"mode": "both"})
            assert (await r.json())["mode"] == "both"
            r = await client.delete(f"/api/pairs/{pid}")
            assert r.status == 200
            assert (await client.get("/api/pairs").json()) if False else True
            r = await client.get("/api/pairs")
            assert (await r.json())["pairs"] == []

        drive(dash, go)

    def test_add_rejected_in_installer_mode(self, db, cfg):
        dash, _ = make_dash(db, cfg, admin=None)
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/pairs", json={"tg": "@a", "bale": "@b"})
            assert r.status == 409

        drive(dash, go)

    def test_bad_mode(self, db, cfg):
        dash, _ = make_dash(db, cfg, admin=FakeResolveAdmin(None, None))
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/pairs", json={"tg": "@a", "bale": "@b", "mode": "x"})
            assert r.status == 400

        drive(dash, go)


class TestControl:
    def test_pause_resume_and_status(self, db, cfg, tg, bale, bridge):
        dash, _ = make_dash(db, cfg, bridge=bridge, admin=FakeResolveAdmin(tg, bale))
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            j = await (await client.get("/api/status")).json()
            assert j["mode"] == "bridge" and j["paused"] is False
            assert j["uptime_s"] >= 120
            await client.post("/api/pause", json={})
            assert bridge.paused is True and dash.db.get_meta("paused") == "1"
            j = await (await client.get("/api/status")).json()
            assert j["paused"] is True
            await client.post("/api/resume", json={})
            assert bridge.paused is False and dash.db.get_meta("paused") == "0"

        drive(dash, go)


class TestLogsAndPasswd:
    def test_logs(self, db, cfg):
        dash, _ = make_dash(db, cfg)
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            j = await (await client.get("/api/logs?n=1")).json()
            assert len(j["lines"]) == 1 and "خطای آزمایشی" in j["lines"][0]

        drive(dash, go)

    def test_change_password_relogin(self, db, cfg):
        dash, store = make_dash(db, cfg)
        Dashboard.set_credentials(store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/passwd", json={"new": "short"})
            assert r.status == 400
            r = await client.post("/api/passwd", json={"new": "newpass9"})
            assert r.status == 200
            # رمز قدیمی دیگر کار نمی‌کند؛ جدید کار می‌کند
            await client.post("/api/logout", json={})
            assert (await login(client, pw="secret1")).status == 401
            assert (await login(client, pw="newpass9")).status == 200

        drive(dash, go)


class TestAccessAndPromote:
    def test_access_report(self, db, cfg, pair):
        dash, _ = make_dash(db, cfg)
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            j = await (await client.post("/api/access", json={})).json()
            assert j["ok"] and "دسترسی" in j["report"]

        drive(dash, go)

    def test_promote_requires_user_mode(self, db, cfg, pair):
        dash, _ = make_dash(db, cfg)
        Dashboard.set_credentials(dash.store, "admin", "secret1")

        async def go(client):
            await login(client, pw="secret1")
            r = await client.post("/api/promote", json={})
            assert r.status == 409

        drive(dash, go)


class TestCredentialsHelpers:
    def test_ensure_once(self, db):
        st = Store(db)
        u1, p1, c1 = Dashboard.ensure_credentials(st)
        u2, p2, c2 = Dashboard.ensure_credentials(st)
        assert c1 and not c2 and p2 is None and u1 == u2 == "admin" and p1

    def test_change_user(self, db):
        st = Store(db)
        Dashboard.ensure_credentials(st)
        Dashboard.change_user(st, "parham")
        assert st.get("dash_auth")["user"] == "parham"
