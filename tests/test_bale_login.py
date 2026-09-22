"""تست‌های موتور ورود سلف بله (BaleLoginEngine) — آفلاین با کلاینت جعلی."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bridge.bale import login as login_mod
from bridge.bale.login import BaleLoginEngine
from tests.conftest import run


class _Resp:
    """پاسخ موفق aiobale — با هش تراکنش اختیاری."""

    def __init__(self, txn: str | None = "TX1") -> None:
        self.transaction_hash = txn


@pytest.fixture
def fake(monkeypatch):
    class AuthErrors:  # کلاس نشانه — هم‌شکل aiobale.enums.AuthErrors
        pass

    class Err(AuthErrors):
        name = "BAD_NUMBER"

    built: list = []

    class FakeClient:
        phone_resp: object = None
        code_resp: object = None

        def __init__(self, session_file=None, phone_number=None) -> None:
            self.session_file = session_file
            self.phone_number = phone_number
            built.append(self)

        async def start_phone_auth(self, phone: int):
            r = type(self).phone_resp
            if isinstance(r, BaseException):
                raise r
            return r

        async def validate_code(self, code, txn):
            r = type(self).code_resp
            if isinstance(r, BaseException):
                raise r
            return r

    monkeypatch.setattr(login_mod, "Client", FakeClient)
    monkeypatch.setattr(login_mod, "AuthErrors", AuthErrors)
    return SimpleNamespace(FakeClient=FakeClient, Err=Err, Resp=_Resp, built=built)


# ───────────────────────────── نشست ─────────────────────────────

def test_session_path_normalizes_suffix_and_makes_dirs(tmp_path):
    eng = BaleLoginEngine(str(tmp_path / "sub" / "sess"))
    p = eng.session_path()
    assert p.name == "sess.bale"
    assert p.parent.is_dir()


def test_session_path_keeps_bale_suffix(tmp_path):
    eng = BaleLoginEngine(str(tmp_path / "already.bale"))
    assert eng.session_path().name == "already.bale"


def test_build_client_passes_session_and_phone(fake, tmp_path):
    eng = BaleLoginEngine(str(tmp_path / "s.bale"), "+989120000000")
    c = eng.build_client()
    assert fake.built[-1] is c
    assert c.phone_number == "+989120000000"
    assert str(c.session_file).endswith("s.bale")


# ───────────────────── درخواست کد (مرحلهٔ ۱) ─────────────────────

def test_request_code_success_stores_txn(fake, tmp_path):
    fake.FakeClient.phone_resp = fake.Resp("TX1")
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    ok, info = run(eng.request_code("+989120000000"))
    assert ok and info == "کد ارسال شد"
    assert eng.pending


def test_request_code_auth_error(fake, tmp_path):
    fake.FakeClient.phone_resp = fake.Err()
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    ok, info = run(eng.request_code("+98912"))
    assert not ok and "BAD_NUMBER" in info
    assert not eng.pending


def test_request_code_invalid_server_response(fake, tmp_path):
    fake.FakeClient.phone_resp = _Resp(txn=None)
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    ok, info = run(eng.request_code("+98912"))
    assert not ok and "نامعتبر" in info


def test_request_code_network_error(fake, tmp_path):
    fake.FakeClient.phone_resp = TimeoutError("slow")
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    ok, info = run(eng.request_code("+98912"))
    assert not ok and "TimeoutError" in info


# ───────────────────── تأیید کد (مرحلهٔ ۲) ─────────────────────

def test_validate_requires_pending_request(tmp_path):
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    ok, info = run(eng.validate_code("12345"))
    assert not ok and "اول شماره" in info


def test_validate_success_clears_txn(fake, tmp_path):
    fake.FakeClient.phone_resp = fake.Resp("TX1")
    fake.FakeClient.code_resp = _Resp(txn=None)
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    run(eng.request_code("+98912"))
    ok, info = run(eng.validate_code("12345"))
    assert ok and info == "نشست ذخیره شد"
    assert not eng.pending


def test_validate_auth_error_keeps_txn(fake, tmp_path):
    fake.FakeClient.phone_resp = fake.Resp("TX1")
    fake.FakeClient.code_resp = fake.Err()
    eng = BaleLoginEngine(str(tmp_path / "s.bale"))
    run(eng.request_code("+98912"))
    ok, info = run(eng.validate_code("00000"))
    assert not ok and "BAD_NUMBER" in info
    assert eng.pending  # کد اشتباه → تراکنش برای تلاش دوباره می‌ماند


# ───────────────────── اتصال به ویزارد و اسکریپت ─────────────────────

def test_wizard_delegates_login_to_engine(fake, tmp_path, monkeypatch):
    from bridge.wizard import Wizard

    monkeypatch.setattr("bridge.wizard.BaleLoginEngine", BaleLoginEngine, raising=False)
    w = Wizard(api=None, db=None, cfg=SimpleNamespace(
        BALE_SESSION=str(tmp_path / "w"), BALE_PHONE="+989121111111"), store=None)
    assert isinstance(w._bale_login, BaleLoginEngine)
    assert w._bale_login.phone == "+989121111111"

    fake.FakeClient.phone_resp = fake.Resp("TX2")
    ok, _ = run(w._bale_request_code("+989121111111"))
    assert ok and w._bale_login.pending
    ok, _ = run(w._bale_validate(999, "12345"))
    assert ok and not w._bale_login.pending


def test_login_bale_script_delegates_to_engine(monkeypatch, tmp_path):
    import login_bale

    called: dict = {}

    class FakeEngine:
        def __init__(self, session_file, phone=None) -> None:
            called["args"] = (session_file, phone)

        def run_interactive(self) -> int:
            called["ran"] = True
            return 0

    monkeypatch.setattr(login_bale, "BaleLoginEngine", FakeEngine)
    monkeypatch.setattr(login_bale.cfg, "BALE_SESSION", str(tmp_path / "x"))
    monkeypatch.setattr(login_bale.cfg, "BALE_PHONE", "+98912")
    assert login_bale.main() == 0
    assert called["ran"]
    assert called["args"] == (str(tmp_path / "x"), "+98912")
