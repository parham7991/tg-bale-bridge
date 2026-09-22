"""تست‌های بستهٔ بافر لاگ (bridge/logbuf) — آفلاین."""
from __future__ import annotations

import logging

import bridge.logbuf as lb
from bridge.logbuf import DEFAULT_CAPACITY, InstallEngine, RingBufferHandler, RingEngine

# ───────────────────────────── RingEngine ─────────────────────────────

def test_ring_capacity_and_tail():
    r = RingEngine(3)
    for i in range(5):
        r.append(f"L{i}")
    assert len(r) == 3                       # قدیمی‌ها حذف شده‌اند
    assert r.tail(2) == ["L3", "L4"]
    assert r.tail(99) == ["L2", "L3", "L4"]  # بیشتر از موجودی → همه


def test_ring_tail_clamp_bounds():
    r = RingEngine(10)
    r.append("x")
    assert r.tail(0) == ["x"]                # 0 → حداقل ۱
    assert r.tail(-5) == ["x"]
    r2 = RingEngine(5)
    for i in range(5):
        r2.append(f"a{i}")
    assert len(r2.tail(10_000)) == 5         # سقف TAIL_MAX منطقی


# ───────────────────────────── RingBufferHandler ─────────────────────────────

def test_handler_emit_formats_and_swallow_errors():
    h = RingBufferHandler(50)
    rec = logging.LogRecord("n", logging.INFO, "p", 1, "پیام %s", ("تست",), None)
    h.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    h.emit(rec)
    assert h.tail(1) == ["INFO پیام تست"]
    h.emit(object())                         # رکورد خراب → نباید exception بدهد
    assert len(h.tail(50)) == 1
    assert h.lines.maxlen == 50


def test_handler_lines_alias_is_same_deque():
    h = RingBufferHandler()
    assert h.lines is h.ring.lines           # سازگاری با کد قدیمی
    assert h.lines.maxlen == DEFAULT_CAPACITY


# ───────────────────────────── InstallEngine / install ─────────────────────────────

def test_install_attaches_to_root_and_formats():
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        h = InstallEngine.install(capacity=7)
        assert any(h is x for x in root.handlers)
        assert h.level == logging.INFO
        rec = logging.LogRecord("mod", logging.WARNING, "p", 1, "هشدار", (), None)
        h.emit(rec)
        line = h.tail(1)[0]
        assert "WARNING" in line and "هشدار" in line and "mod" in line
        assert h.lines.maxlen == 7
    finally:
        for x in list(root.handlers):
            if x not in before:
                root.removeHandler(x)


def test_package_surface_is_legacy():
    assert callable(lb.install)
    assert lb.RingBufferHandler is RingBufferHandler
    assert isinstance(lb.VERSION, str)
