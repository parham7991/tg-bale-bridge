"""ساخت سشن تلگرام — یک بار قبل از اجرای main.py اجرا کنید."""
import asyncio

from telethon import TelegramClient

import config as cfg


async def main():
    if not cfg.TG_API_ID or not cfg.TG_API_HASH:
        print("ابتدا TG_API_ID و TG_API_HASH را در .env بگذارید (از my.telegram.org).")
        return
    client = TelegramClient(str(cfg.SESSION_PATH), cfg.TG_API_ID, cfg.TG_API_HASH)
    await client.start(phone=cfg.TG_PHONE or None)
    me = await client.get_me()
    print(f"✅ ورود موفق: {me.first_name} (id={me.id}, username=@{me.username or '-'})")
    print(f"فایل سشن ذخیره شد: {cfg.SESSION_PATH}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
