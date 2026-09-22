#!/usr/bin/env python3
"""One-time login for the Bale **selfbot** (user account via aiobale).

Run this *once* before starting ``main.py`` with ``BALE_MODE=user``:

    python login_bale.py

It opens an interactive session: enter your Bale phone number, then the SMS
code.  The login token is saved to ``data/session.bale`` and reused on every
run — no password is stored.

Why a selfbot?  New Bale versions refuse to add bots to channels, so a bot can
never post there.  Your own user account *is* a channel member and can post
with no bot involved at all.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aiobale import Client  # noqa: E402

import config as cfg  # noqa: E402


def main() -> int:
    sess = cfg.BALE_SESSION
    sess_path = Path(sess)
    sess_path = sess_path if sess_path.suffix == ".bale" else sess_path.with_suffix(".bale")
    sess_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print("  ورود به حساب کاربری بله (سلف‌بات با aiobale)")
    print("=" * 56)
    print(f"فایل نشست: {sess_path}")
    if cfg.BALE_PHONE:
        print(f"شماره تلفن: {cfg.BALE_PHONE}")
    else:
        print("شماره تلفن را هنگام درخواست وارد کنید (BALE_PHONE هم قابل تنظیم است).")
    print("کد پیامکی را وارد کنید… (خروج: Ctrl+C)")
    print()

    client = Client(session_file=sess, phone_number=cfg.BALE_PHONE or None)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nلغو شد.")
        return 1
    print()
    print("✔ ورود موفق — نشست ذخیره شد.")
    print("  حالا BALE_MODE=user را در .env بگذارید و main.py را اجرا کنید.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
