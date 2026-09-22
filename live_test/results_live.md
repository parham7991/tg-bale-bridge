# 🧪 گزارش تست زندهٔ سلف‌بات بله — v1.2.1

**تاریخ:** 2026-09-22 · **محیط اجرا:** سرور `omniroute-arena` (Ubuntu 22.04، پایتون 3.10) · **حساب:** واقعی (+989•••••4064)

## نتیجه نهایی: ۶/۶ PASS ✅

```
PASS  T0_connect        websocket handshake
PASS  T1_get_me         id=2020722119 name='Parham'
PASS  T2_send_text      message_id=1759265211188305
PASS  T3_edit_event     echo رویداد ویرایش رسید
PASS  T4_send_photo     message_id=3284303876240462
PASS  T5_delete_event   echo حذف: message_ids=[1759265211188305]
```

## رویدادهای زنده با ترافیک واقعی

| رویداد | نمونه واقعی دریافت‌شده |
|---|---|
| `message` | پیام گروه واقعی با متن/کپشن/ریپلای کامل |
| `edited_message` | `"text": "FINAL-OK EDITED"` |
| `deleted_messages` ⭐ | `{'chat': {'id': 192381766, 'type': 'group'}, 'message_ids': [7797696629510781257, -1176260706472685736]}` — حذفِ **دیگر اعضا** در گروه! |

➡️ یعنی همگام‌سازی حذف بله→تلگرام (که با رباتِ رسمی هرگز ممکن نبود) واقعاً کار می‌کند.

## باگ‌هایی که در تست زنده پیدا و رفع شد

1. **ثبت هندلر dispatcher** — `dp.message(fn)` در aiobale تابع را «فیلتر» ثبت می‌کرد نه هندلر
   (۰ هندلر!) → فرم درست: `dp.message()(fn)` — کشف با دیباگ فریم‌به‌فریم وب‌سوکت.
2. **get_me/get_chat** — نام از `client.me.user` خوانده شود + باز کردن wrapperها (String)
   + آرگومان اجباری `chat_type` در `load_user`.
3. **`load_history` کتابخانه aiobale** روی پیام‌های فرستاده‌شده از API خطای parse می‌دهد
   (باگ مدل `MessageData` در خود کتابخانه) — باتری تست رویدادمحور شد و پل هرگز از آن
   استفاده نمی‌کند.

## نکات اجرا

- بله اتصال TLS از برخی رنج‌های دیتاسنتر خارجی را رد می‌کند؛ تست از سروری که به
  `next-ws.bale.ai` دسترسی دارد اجرا شد (کیت: `python live_test/local_kit.py all`).
- همهٔ پیام‌های آزمایشی در پیام‌های ذخیره‌شدهٔ خودمان بود و آخر تست حذف شدند.

## وضعیت فایل‌ها روی سرور (طبق خواسته، چیزی پاک نشده)

- `/root/tg-bale-bridge/` — کلون ریپو (کامیت 0379eb7) + venv + نشست
- `/root/tg-bale-bridge/live_test/session.bale` — ⚠️ نشست لاگین حساب بله؛ هر وقت گفتی پاکش کنم
- `live_test/results.json`, `probe.py.scp-backup`, `events_nohup.log` — خروجی‌های تست

**منتشر شده:** https://github.com/parham7991/tg-bale-bridge/releases/tag/v1.2.1
