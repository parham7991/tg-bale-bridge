#!/usr/bin/env python3
"""پروب نهایی v3 — چاپ مستقیم خروجی آداپتور (بدون normalize تکراری)."""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
from bridge.bale_user import BaleUserAPI  # noqa: E402

RECEIVED = []
api = BaleUserAPI(session_file="live_test/session.bale", db=None)


async def handler(upd, off):
    kind = next(iter(upd), "?")
    RECEIVED.append(kind)
    body = json.dumps(upd[kind], ensure_ascii=False, default=str)[:220]
    print("HANDLER[{}] {}".format(kind, body), flush=True)


async def main():
    task = asyncio.create_task(api.listen(handler))
    await asyncio.sleep(3)
    print("... listening 30s — send from phone NOW ...", flush=True)
    await asyncio.sleep(30)

    me = await api.get_me()
    sid = int(me["id"])
    res = await api.send_message(sid, "FINAL-OK {}".format(int(time.time())))
    mid = res["message_id"]
    await asyncio.sleep(5)
    await api.edit_message_text(sid, mid, "FINAL-OK EDITED")
    await asyncio.sleep(5)
    await api.delete_message(sid, mid)
    await asyncio.sleep(10)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    try:
        await api.close()
    except Exception:
        pass
    print("\nKINDS: {}".format(RECEIVED), flush=True)
    ok = ("message" in RECEIVED and "edited_message" in RECEIVED and "deleted_messages" in RECEIVED)
    print("VERDICT: {}".format("ALL-THREE OK" if ok else "PARTIAL"), flush=True)


asyncio.run(main())
