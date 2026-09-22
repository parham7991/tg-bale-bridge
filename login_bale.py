#!/usr/bin/env python3
"""One-time login for the Bale **selfbot** — thin wrapper over ``bridge.bale.login``.

Run this *once* before starting ``main.py`` with ``BALE_MODE=user``:

    python login_bale.py

All logic lives in ``bridge/bale/login.py`` (class ``BaleLoginEngine``); this
script only invokes it.  The login token is saved to ``data/session.bale``
and reused on every run — no password is stored.

Why a selfbot?  New Bale versions refuse to add bots to channels, so a bot can
never post there.  Your own user account *is* a channel member and can post
with no bot involved at all.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config as cfg  # noqa: E402
from bridge.bale import BaleLoginEngine  # noqa: E402


def main() -> int:
    return BaleLoginEngine(cfg.BALE_SESSION, cfg.BALE_PHONE or None).run_interactive()


if __name__ == "__main__":
    sys.exit(main())
