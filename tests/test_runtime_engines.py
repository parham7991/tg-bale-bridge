"""تست‌های بستهٔ چرخهٔ اجرا (bridge/runtime) — آفلاین با فیک‌های کامل."""
from __future__ import annotations

from types import SimpleNamespace

from bridge.runtime import VERSION, OverridesEngine
from bridge.runtime.lifecycle import LifecycleEngine
from bridge.runtime.types_map import BANNER, is_installer_mode
from tests.conftest import run


class FakeStore:
    def __init__(self, admin=0, tg_api=None, bale_bot=None, installed=False):
        self._admin, self._api, self._bb, self._installed = admin, tg_api, bale_bot, installed

    def admin_tg_id(self):
        return self._admin

    def tg_api(self):
        return self._api

    def bale_bot(self):
        return self._bb

    def installed(self, cfg):
        return self._installed

    def bale_self(self):
        return None


# ───────────────────────────── types_map ─────────────────────────────

def test_banner_and_installer_mode():
    assert "تلگرام" in BANNER and "بله" in BANNER
    cfg = SimpleNamespace(TG_API_ID=1, TG_API_HASH="h")
    assert is_installer_mode(cfg, FakeStore(installed=False)) is True
    assert is_installer_mode(cfg, FakeStore(installed=True)) is False


# ───────────────────────────── OverridesEngine ─────────────────────────────

def test_overrides_fill_only_blanks():
    cfg = SimpleNamespace(ADMIN_TG_ID=0, TG_API_ID=0, TG_API_HASH="", BALE_TOKEN="")
    st = FakeStore(admin=555, tg_api={"api_id": 7, "api_hash": "h7"},
                   bale_bot={"token": "T:K"})
    OverridesEngine(st).apply(cfg)
    assert cfg.ADMIN_TG_ID == 555 and cfg.TG_API_ID == 7
    assert cfg.TG_API_HASH == "h7" and cfg.BALE_TOKEN == "T:K"


def test_overrides_env_wins():
    cfg = SimpleNamespace(ADMIN_TG_ID=111, TG_API_ID=1, TG_API_HASH="env",
                          BALE_TOKEN="env:tok")
    st = FakeStore(admin=555, tg_api={"api_id": 7, "api_hash": "h7"},
                   bale_bot={"token": "T:K"})
    OverridesEngine(st).apply(cfg)
    assert cfg.ADMIN_TG_ID == 111 and cfg.TG_API_ID == 1
    assert cfg.TG_API_HASH == "env" and cfg.BALE_TOKEN == "env:tok"


# ───────────────────────────── LifecycleEngine ─────────────────────────────

def test_build_tasks_with_and_without_bots():
    closed = {"bale": 0, "tgbot": 0, "bbot": 0, "dash": 0}

    class FakeTG:
        def run_until_disconnected(self):
            return _done()

    class FakeBale:
        def listen(self, handler, offset=None, timeout=None):
            return _done(("bale", offset, timeout))

        async def close(self):
            closed["bale"] += 1

    class FakeBridge:
        def workers(self):
            return [_done("w1"), _done("w2")]

    class FakeRouter:
        def handle_update(self, upd, offset):
            pass

        def panel_handler(self, api):
            return handler

    async def handler(upd, offset):
        pass

    async def _done(v=None):
        return v

    db = SimpleNamespace(get_meta=lambda k: {"bale_offset": "20",
                                             "bale_bot_offset": "70"}.get(k))
    cfg = SimpleNamespace(BALE_POLL_TIMEOUT=25, DASH_ENABLED=True)
    lc = LifecycleEngine(cfg, db)

    class FakeBotAPI:
        def __init__(self, name):
            self.name = name

        def listen(self, h, offset=None, timeout=None):
            return _done((self.name, offset, timeout))

        async def close(self):
            closed[self.name] += 1

    tg_bot_task = _done("tgbot")
    bale_bot_api = FakeBotAPI("bbot")

    tasks = lc.build_tasks(FakeTG(), FakeBale(), FakeBridge(), FakeRouter(),
                           tg_bot_task=tg_bot_task, bale_bot_api=bale_bot_api)
    assert len(tasks) == 6                      # tg + bale + 2worker + tgbot + bbot
    # آفست‌ها از متا خوانده شده‌اند (بیلدر فقط می‌سازد، اجرا نمی‌کند)
    assert db.get_meta("bale_offset") == "20"

    class FakeDash:
        async def stop(self):
            closed["dash"] += 1

    async def runner():
        gather_tasks = lc.build_tasks(FakeTG(), FakeBale(), FakeBridge(), FakeRouter(),
                                      tg_bot_task=None, bale_bot_api=None)
        # همه coroutineهای بی‌خطر — gather سریع تمام می‌شود
        await lc.run_all(gather_tasks, dash=FakeDash(), tg_bot_api=None,
                         bale_bot_api=None, bale=FakeBale())
    run(runner())
    assert closed == {"bale": 1, "tgbot": 0, "bbot": 0, "dash": 1}


def test_run_all_closes_everything_on_error():
    closed = []

    async def boom():
        raise RuntimeError("x")

    async def ok():
        pass

    class FakeBale:
        async def close(self):
            closed.append("bale")

    class FakeBot:
        def __init__(self, name):
            self.name = name

        async def close(self):
            closed.append(self.name)

    class FakeDash:
        async def stop(self):
            closed.append("dash")

    cfg = SimpleNamespace(DASH_ENABLED=True)
    lc = LifecycleEngine(cfg, SimpleNamespace(get_meta=lambda k: None))
    try:
        run(lc.run_all([ok(), boom(), ok()],
                       dash=FakeDash(), tg_bot_api=FakeBot("tgbot"),
                       bale_bot_api=FakeBot("bbot"), bale=FakeBale()))
        raised = False
    except RuntimeError:
        raised = True
    assert raised                                # خطا بالا می‌آید
    assert closed == ["dash", "tgbot", "bbot", "bale"]   # ترتیب دقیق پاک‌سازی


# ───────────────────────────── سازگاری ─────────────────────────────

def test_package_surface_and_version():
    assert VERSION == "2.17.4"
    assert hasattr(OverridesEngine, "apply")


def test_runtime_cli_does_not_run_on_import():
    # ایمپورت ماژول نباید لاگ/حلقه راه بیندازد — فقط کلاس بده
    import bridge.runtime as rt
    assert callable(rt.Runtime.cli)
