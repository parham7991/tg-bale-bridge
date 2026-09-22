#!/usr/bin/env python3
"""کیت تست زندهٔ سلف‌بات بله — روی سیستم خودتان (IP ایران) اجرا کنید.

    python live_test/local_kit.py all              # کامل: لاگین + باتری تست + تست رویدادها
    python live_test/local_kit.py login            # فقط ورود (شماره + کد پیامکی)
    python live_test/local_kit.py tests            # باتری تست T0..T7
    python live_test/local_kit.py events 120       # گوش‌دادن به رویدادها (حذف!)
    python live_test/local_kit.py request-code +989...   # ارسال کد (بدون تعامل)
    python live_test/local_kit.py verify 12345     # تایید کد (بدون تعامل)

نتیجه: چاپ PASS/FAIL + فایل‌های live_test/results.json و live_test/events.jsonl
(نشست و نتایج هرگز به git نمی‌روند — در .gitignore هستند.)

توضیح: بله اتصال TLS از IPهای خارج از ایران را می‌بندد؛ این کیت باید از یک
اینترنت ایرانی اجرا شود. همهٔ تست‌ها روی «پیام‌های ذخیره‌شده» خودتان انجام
می‌شود و در پایان پیام‌های آزمایشی حذف می‌شوند.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiobale import Client  # noqa: E402
from aiobale.enums import AuthErrors, ChatType  # noqa: E402

from bridge.bale_user import BaleUserAPI  # noqa: E402

HERE = Path(__file__).parent
SESSION = HERE / "session.bale"
RESULTS = HERE / "results.json"
EVENTS = HERE / "events.jsonl"
TXN = HERE / "txn.json"

# کوچک‌ترین PNG معتبر (۱×۱ قرمز)
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc00000030101cf34cc69000000004945"
    "4e44ae426082"
)


def _normalize(phone: str) -> int:
    s = str(phone).strip().replace("+", "").replace(" ", "")
    if s.startswith("09"):
        s = "98" + s[1:]
    elif s.startswith("00"):
        s = s[2:]
    if not s.isdigit():
        raise ValueError(f"bad phone: {phone!r}")
    return int(s)


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, default=str))


# ───────────────────────────── ورود ─────────────────────────────

async def cmd_request_code(argv: list[str]) -> int:
    phone = _normalize(argv[0])
    client = Client(session_file=SESSION)
    try:
        resp = await asyncio.wait_for(client.start_phone_auth(phone), timeout=45)
    except asyncio.TimeoutError:
        print(json.dumps({"ok": False, "error": "timeout — سرور جواب نداد (IP خارجی؟)"}))
        return 2
    if isinstance(resp, AuthErrors):
        print(json.dumps({"ok": False, "error": f"AuthErrors.{resp.name}"}))
        return 3
    _dump(TXN, {"transaction_hash": resp.transaction_hash, "phone": phone})
    print(json.dumps({"ok": True, "phone": phone,
                      "sent_via": str(getattr(resp, "sent_code_type", "?"))},
                     ensure_ascii=False))
    return 0


async def cmd_verify(argv: list[str]) -> int:
    code = argv[0].strip()
    if not TXN.exists():
        print(json.dumps({"ok": False, "error": "txn.json نیست — اول request-code"}))
        return 1
    txn = json.loads(TXN.read_text())
    client = Client(session_file=SESSION)
    try:
        resp = await asyncio.wait_for(
            client.validate_code(code, txn["transaction_hash"]), timeout=45)
    except asyncio.TimeoutError:
        print(json.dumps({"ok": False, "error": "timeout"}))
        return 2
    if isinstance(resp, AuthErrors):
        print(json.dumps({"ok": False, "error": f"AuthErrors.{resp.name}"}))
        return 3
    print(json.dumps({"ok": True, "client_id": getattr(client, "id", None),
                      "session_file": str(SESSION),
                      "session_bytes": SESSION.stat().st_size if SESSION.exists() else 0},
                     ensure_ascii=False))
    return 0


async def cmd_login(argv: list[str]) -> int:
    """ورود تعاملی — روی ترمینال خودتان (tty) با CLI خود aiobale."""
    phone = _normalize(argv[0]) if argv else None
    client = Client(session_file=SESSION, phone_number=phone)
    await client._ensure_token_exists()  # اگر نشست باشد بی‌صدا برمی‌گردد؛ وگرنه CLI ورود
    print(json.dumps({"ok": True, "client_id": getattr(client, "id", None),
                      "session_file": str(SESSION),
                      "already_or_now_logged": True}, ensure_ascii=False))
    return 0


# ───────────────────────────── باتری تست ─────────────────────────────

async def battery() -> list:
    results: list = []

    def rec(name: str, ok: bool, detail: str = "") -> None:
        results.append({"test": name, "ok": bool(ok), "detail": str(detail)[:400]})
        print(("PASS" if ok else "FAIL") + f"  {name}  {detail}", flush=True)

    photo_path = HERE / "test_pixel.png"
    photo_path.write_bytes(PNG_1PX)
    api = BaleUserAPI(session_file=SESSION, db=None)

    try:
        await asyncio.wait_for(api.start(), timeout=40)
        rec("T0_connect", True, "websocket handshake")
    except Exception as e:
        rec("T0_connect", False, f"{type(e).__name__}: {e}")
        _dump(RESULTS, results)
        return results

    try:
        me = await asyncio.wait_for(api.get_me(), timeout=30)
        rec("T1_get_me", bool(me.get("id")), f"id={me.get('id')} name={me.get('first_name')!r}")
        self_id = int(me["id"])
    except Exception as e:
        rec("T1_get_me", False, f"{type(e).__name__}: {e}")
        _dump(RESULTS, results)
        return results

    marker = f"BRIDGE-LIVE {int(time.time())}"
    text_mid = None

    try:
        res = await asyncio.wait_for(
            api.send_message(self_id, f"{marker} — سلام از سلف‌بات بله! ✅"), timeout=30)
        text_mid = res.get("message_id")
        rec("T2_send_text", bool(text_mid), f"message_id={text_mid}")
    except Exception as e:
        rec("T2_send_text", False, f"{type(e).__name__}: {e}")

    try:
        hist = await asyncio.wait_for(
            api.client.load_history(self_id, ChatType.PRIVATE, limit=5), timeout=30)
        found = [m for m in hist if getattr(m, "message_id", None) == text_mid]
        norm = api.normalize(found[0]) if found else None
        ok = bool(norm and norm.get("text") and marker in norm["text"])
        rec("T3_history_normalize", ok, json.dumps(norm, ensure_ascii=False, default=str)[:250])
    except Exception as e:
        rec("T3_history_normalize", False, f"{type(e).__name__}: {e}")

    try:
        await asyncio.wait_for(
            api.edit_message_text(self_id, text_mid, f"{marker} — ویرایش شد ✏️"), timeout=30)
        hist = await asyncio.wait_for(
            api.client.load_history(self_id, ChatType.PRIVATE, limit=5), timeout=30)
        edited = [m for m in hist if getattr(m, "message_id", None) == text_mid]
        ok = bool(edited) and "ویرایش شد" in (api.normalize(edited[0]).get("text") or "")
        rec("T4_edit", ok, "load_history confirms new text")
    except Exception as e:
        rec("T4_edit", False, f"{type(e).__name__}: {e}")

    photo_mid = None
    try:
        res = await asyncio.wait_for(
            api.send_photo(self_id, photo_path, caption=f"{marker} عکس تست"), timeout=60)
        photo_mid = res.get("message_id")
        ok = bool(photo_mid) and all(v is not None for v in api._files.values())
        rec("T5_send_photo", ok, f"message_id={photo_mid} file_cache={list(api._files)[:3]}")
    except Exception as e:
        rec("T5_send_photo", False, f"{type(e).__name__}: {e}")

    try:
        if photo_mid:
            await asyncio.wait_for(api.delete_message(self_id, photo_mid), timeout=30)
        await asyncio.wait_for(api.delete_message(self_id, text_mid), timeout=30)
        rec("T6_delete", True, f"deleted text={text_mid} photo={photo_mid}")
    except Exception as e:
        rec("T6_delete", False, f"{type(e).__name__}: {e}")

    try:
        await asyncio.sleep(2)
        hist = await asyncio.wait_for(
            api.client.load_history(self_id, ChatType.PRIVATE, limit=10), timeout=30)
        ids = {getattr(m, "message_id", None) for m in hist}
        rec("T7_delete_verified", text_mid not in ids and photo_mid not in ids,
            "پیام‌های آزمایشی دیگر در تاریخچه نیستند")
    except Exception as e:
        rec("T7_delete_verified", False, f"{type(e).__name__}: {e}")

    await api.close()
    photo_path.unlink(missing_ok=True)
    _dump(RESULTS, results)
    return results


async def cmd_tests(argv: list[str]) -> int:
    results = await battery()
    passed = sum(1 for r in results if r["ok"])
    print(f"\n=== {passed}/{len(results)} passed → {RESULTS} ===")
    return 0 if passed == len(results) else 1


# ───────────────────────────── رویدادها ─────────────────────────────

async def cmd_events(argv: list[str]) -> int:
    duration = int(argv[0]) if argv else 120
    EVENTS.write_text("")
    api = BaleUserAPI(session_file=SESSION, db=None)
    await api.start()
    print(f" گوش می‌دهم {duration} ثانیه …", flush=True)
    print(" حالا در اپ بله، در «پیام‌های ذخیره‌شده»:", flush=True)
    print("   ۱) یک پیام بفرست  ۲) ویرایشش کن  ۳) حذفش کن", flush=True)

    async def handler(upd, offset):
        with EVENTS.open("a") as f:
            f.write(json.dumps({"t": time.time(), "update": upd},
                               ensure_ascii=False, default=str) + "\n")
        print(f"  event: {next(iter(upd), '?')}", flush=True)

    task = asyncio.create_task(api.listen(handler))
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=duration)
    except asyncio.TimeoutError:
        pass
    task.cancel()
    await api.close()
    lines = [json.loads(ln) for ln in EVENTS.read_text().splitlines() if ln.strip()]
    kinds = [next(iter(e["update"]), "?") for e in lines]
    summary = {"events": len(lines), "kinds": kinds,
               "has_message": "message" in kinds,
               "has_edited": "edited_message" in kinds,
               "has_deleted": "deleted_messages" in kinds}
    print(json.dumps(summary, ensure_ascii=False))
    _dump(HERE / "events_summary.json", summary)
    return 0


async def cmd_all(argv: list[str]) -> int:
    print("── مرحله ۱: ورود ──", flush=True)
    if SESSION.exists():
        print(f"نشست از قبل هست: {SESSION} (لاگین رد شد)")
    else:
        phone = input("شماره بله (مثلاً +98912...): ").strip()
        await cmd_login([phone])
    print("\n── مرحله ۲: باتری تست ──", flush=True)
    results = await battery()
    passed = sum(1 for r in results if r["ok"])
    if passed < len(results):
        print("\n=== %d/%d — باتری کامل پاس نشد؛ تست رویدادها بعداً ===" % (passed, len(results)))
        return 1
    print("\n── مرحله ۳: تست رویدادها (مخصوصاً «حذف») ──", flush=True)
    prompt = "آماده‌ای؟ در اپ بله پیام بفرست/ویرایش/حذف کن. [Enter=شروع / n=رد شدن] "
    ready = input(prompt).strip().lower()
    if ready != "n":
        await cmd_events(["120"])
    print("\n🎉 همهٔ تست‌ها تمام شد — خروجی بالا و فایل results.json را برای من بفرست.")
    return 0


COMMANDS = {
    "request-code": cmd_request_code,
    "verify": cmd_verify,
    "login": cmd_login,
    "tests": cmd_tests,
    "events": cmd_events,
    "all": cmd_all,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return asyncio.run(COMMANDS[sys.argv[1]](sys.argv[2:]))


if __name__ == "__main__":
    sys.exit(main())
