"""تست مستقیم موتورهای داشبورد — بدون HTTP (هر بخش، یک ماژول، یک موتور)."""
from __future__ import annotations

import pytest

from bridge.dashboard import VERSION, AuthEngine
from bridge.dashboard.auth import AuthError
from bridge.dashboard.context import RuntimeCtx
from bridge.dashboard.engines import (
    ControlEngine,
    DashboardError,
    LogsEngine,
    OpsEngine,
    PairsEngine,
    StatusEngine,
)
from bridge.store import Store
from tests.test_dashboard import FakeLogBuf, FakeProbeBale, FakeResolveAdmin, FakeSelfTg


def make_ctx(db, cfg, **rt):
    store = Store(db)
    ctx = RuntimeCtx(db, store, cfg, rt)
    return ctx, store


class Cfg:
    DASH_HOST = "127.0.0.1"
    DASH_PORT = 8080
    BALE_MODE = "bot"


# ───────────────────────────── AuthEngine ─────────────────────────────

class TestAuthEngine:
    def test_ensure_once_and_stable(self, db):
        a = AuthEngine(Store(db))
        u1, p1, created1 = a.ensure_credentials()
        u2, p2, created2 = a.ensure_credentials()
        assert created1 and not created2 and p2 is None
        assert u1 == u2 == "admin" and len(p1) >= 8

    def test_verify_wrong_right(self, db):
        a = AuthEngine(Store(db))
        a.set_credentials("parham", "secret1")
        assert not a.verify("parham", "nope")
        assert not a.verify("other", "secret1")
        assert a.verify("parham", "secret1")

    def test_change_password(self, db):
        a = AuthEngine(Store(db))
        a.set_credentials("admin", "old123")
        a.change_password("newpass9")
        assert not a.verify("admin", "old123")
        assert a.verify("admin", "newpass9")

    def test_change_password_too_short(self, db):
        a = AuthEngine(Store(db))
        with pytest.raises(AuthError):
            a.change_password("abc")

    def test_change_user(self, db):
        a = AuthEngine(Store(db))
        a.ensure_credentials()
        a.change_user("parham")
        assert a.username == "parham"
        assert not a.verify("parham", "whatever")  # فقط نام عوض شد؛ رمز همان قبلی است
        # و با رمز درستِ قبلی هنوز وارد می‌شود:
        a.set_credentials("parham", "secret1")
        assert a.verify("parham", "secret1")

    def test_lockout_flow(self, db):
        a = AuthEngine(Store(db))
        a.set_credentials("admin", "secret1")
        assert not a.check_lock("1.2.3.4")
        for _ in range(4):
            a.register_fail("1.2.3.4")
        assert not a.check_lock("1.2.3.4")
        a.register_fail("1.2.3.4")
        assert a.check_lock("1.2.3.4")
        a.reset_fails("1.2.3.4")
        assert not a.check_lock("1.2.3.4")

    def test_sessions(self, db):
        a = AuthEngine(Store(db))
        t = a.create_session()
        assert a.is_valid(t)
        a.drop_session(t)
        assert not a.is_valid(t)
        assert not a.is_valid("bogus")

    def test_pbkdf2_salted(self, db):
        a = AuthEngine(Store(db))
        a.set_credentials("admin", "samepass")
        h1 = a.record["hash"]
        a.set_credentials("admin", "samepass")
        assert a.record["hash"] != h1  # salt متفاوت → هش متفاوت


# ───────────────────────────── PairsEngine ─────────────────────────────

class TestPairsEngine:
    def test_installer_mode_rejected(self, db, cfg):
        ctx, _ = make_ctx(db, cfg)
        pe = PairsEngine(ctx)
        import asyncio
        with pytest.raises(DashboardError) as ei:
            asyncio.run(pe.add("@a", "@b", "both"))
        assert ei.value.status == 409

    def test_full_flow(self, db, cfg):
        ctx, _ = make_ctx(db, cfg, admin=FakeResolveAdmin(None, None))
        pe = PairsEngine(ctx)
        import asyncio
        pid = asyncio.run(pe.add("@tgpub", "@balepub", "tg2bale"))
        pairs = pe.list()
        assert len(pairs) == 1 and pairs[0]["mode"] == "tg2bale"
        assert pe.set_mode(pid, "both") == "both"
        pe.remove(pid)
        assert pe.list() == []

    def test_bad_mode(self, db, cfg):
        ctx, _ = make_ctx(db, cfg, admin=FakeResolveAdmin(None, None))
        pe = PairsEngine(ctx)
        import asyncio
        with pytest.raises(DashboardError) as ei:
            asyncio.run(pe.add("@a", "@b", "weird"))
        assert ei.value.status == 400


# ───────────────────────────── ControlEngine ─────────────────────────────

class TestControlEngine:
    def test_pause_resume(self, db, cfg, tg, bale, bridge):
        ctx, _ = make_ctx(db, cfg, bridge=bridge)
        ce = ControlEngine(ctx)
        assert ce.state() is False
        assert ce.pause() is True
        assert bridge.paused and ctx.db.get_meta("paused") == "1"
        assert ce.resume() is False
        assert not bridge.paused and ctx.db.get_meta("paused") == "0"

    def test_requires_bridge(self, db, cfg):
        ctx, _ = make_ctx(db, cfg)
        ce = ControlEngine(ctx)
        with pytest.raises(DashboardError) as ei:
            ce.pause()
        assert ei.value.status == 409


# ───────────────────────────── Status/Logs/Ops ─────────────────────────────

class TestStatusLogsOps:
    def test_snapshot_installer(self, db, cfg):
        ctx, store = make_ctx(db, cfg)
        AuthEngine(store).set_credentials("admin", "secret1")
        snap = StatusEngine(ctx).snapshot()
        assert snap["mode"] == "installer" and snap["version"] == VERSION
        assert snap["pairs"] == 0 and "accounts" in snap

    def test_snapshot_bridge_with_control_bot(self, db, cfg, tg, bale, bridge):
        admin = FakeResolveAdmin(tg, bale)
        admin.tg_bot_info = {"id": 7, "username": "ctrl", "token": "SHOULD_NOT_LEAK"}
        ctx, _ = make_ctx(db, cfg, bridge=bridge, admin=admin,
                          tg_me={"id": 999, "username": "selfuser", "token": "X"},
                          bale_me={"id": 42, "username": "baleside"})
        snap = StatusEngine(ctx).snapshot()
        assert snap["mode"] == "bridge" and snap["paused"] is False
        assert snap["accounts"]["control_bot"]["username"] == "ctrl"
        # هیچ توکنی نشت نکند
        assert "SHOULD_NOT_LEAK" not in str(snap) and '"X"' not in str(snap)

    def test_logs_tail(self, db, cfg):
        ctx, _ = make_ctx(db, cfg, log_buffer=FakeLogBuf())
        lines = LogsEngine(ctx).tail(1)
        assert len(lines) == 1 and "خطای آزمایشی" in lines[0]
        assert LogsEngine(ctx).tail(999) is not None

    def test_logs_no_buffer(self, db, cfg):
        ctx, _ = make_ctx(db, cfg)
        assert LogsEngine(ctx).tail(10) == []

    def test_ops_access_report(self, db, cfg, pair):
        ctx, _ = make_ctx(db, cfg, tg=FakeSelfTg(), bale=FakeProbeBale())
        import asyncio
        report = asyncio.run(OpsEngine(ctx).access_report())
        assert "دسترسی" in report and f"#{pair}" in report

    def test_ops_access_empty(self, db, cfg):
        ctx, _ = make_ctx(db, cfg)
        import asyncio
        with pytest.raises(DashboardError) as ei:
            asyncio.run(OpsEngine(ctx).access_report())
        assert ei.value.status == 404

    def test_ops_promote_requires_user_mode(self, db, cfg, pair):
        ctx, _ = make_ctx(db, cfg, bale=object())
        import asyncio
        with pytest.raises(DashboardError) as ei:
            asyncio.run(OpsEngine(ctx).promote_bot())
        assert ei.value.status == 409
