"""بات مدیریت تلگرام — مرکز کنترل: پنل ادمین + ویزارد نصب + دکمه‌های شیشه‌ای."""
from __future__ import annotations

import logging

log = logging.getLogger("tgbot")


class TgAdminBot:
    """بات تلگرامی برای مدیریت پل: دستورات ادمین + ویزارد نصب + کشف شناسه با فوروارد."""

    def __init__(self, api, admin, db, cfg, wizard=None, store=None):
        self.api = api          # BotAPI متصل به api.telegram.org
        self.admin = admin      # ممکن است در حالت نصاب None باشد
        self.db = db
        self.cfg = cfg
        self.wizard = wizard
        self.store = store
        self.me: dict = {}

    async def start(self):
        self.me = await self.api.get_me()
        if self.admin is not None:
            self.admin.tg_bot_info = self.me
        log.info("بات مدیریت تلگرام: @%s (id=%s)",
                 self.me.get("username"), self.me.get("id"))
        if getattr(self.cfg, "ADMIN_TG_ID", 0):
            log.info("ادمین: id=%s", self.cfg.ADMIN_TG_ID)
        else:
            log.warning("ادمین تعیین نشده — اولین /start ادمین می‌شود")
        offset_raw = self.db.get_meta("tgbot_offset")
        offset = int(offset_raw) if offset_raw else None
        await self.api.listen(self.on_update, offset=offset, timeout=30)

    def _is_admin(self, user_id) -> bool:
        return bool(getattr(self.cfg, "ADMIN_TG_ID", 0)
                    and int(user_id) == int(self.cfg.ADMIN_TG_ID))

    async def on_update(self, upd, offset):
        self.db.set_meta("tgbot_offset", str(offset))
        try:
            # ---------- دکمه‌های شیشه‌ای ویزارد ----------
            cb = upd.get("callback_query")
            if cb and self.wizard is not None:
                await self.wizard.handle_callback(cb)
                return

            m = upd.get("message")
            if not m:
                return
            chat = m.get("chat") or {}
            if chat.get("type") != "private":
                return
            uid = (m.get("from") or {}).get("id")
            username = (m.get("from") or {}).get("username") or ""
            text = m.get("text") or ""
            is_forward = bool(
                m.get("forward_from_chat") or m.get("forward_from") or m.get("forward_origin")
            )
            if not text.strip() and not is_forward:
                return

            # ---------- ادمین خودکار: اولین /start ----------
            if not getattr(self.cfg, "ADMIN_TG_ID", 0) and self.store is not None:
                if text.strip() in ("/start", "start", "شروع"):
                    if self.store.claim_admin(uid, username):
                        self.cfg.ADMIN_TG_ID = int(uid)
                        await self.api.send_message(
                            chat.get("id"),
                            f"✅ خوش آمدید! شما ادمین پل شدید (@{username or uid}).\n"
                            "ویزارد نصب را باز می‌کنم…")
                        if self.wizard is not None:
                            await self.wizard.open(chat.get("id"), uid)
                        return
                await self.api.send_message(
                    chat.get("id"),
                    "🔒 این بات قبلاً صاحب دارد. برای انتقال، کلید ADMIN_TG_ID را در .env بگذارید.")
                return

            # ---------- ویزارد ----------
            if self.wizard is not None:
                if text.strip() in ("/setup", "setup", "نصب", "/start") and self._is_admin(uid):
                    await self.wizard.open(chat.get("id"), uid)
                    return
                if self.wizard.is_active(chat.get("id")) and self._is_admin(uid):
                    await self.wizard.handle_text(chat.get("id"), uid, text, m)
                    return

            # ---------- /start غیرادمین ----------
            if text.strip() in ("/start", "start", "شروع") and not self._is_admin(uid):
                await self.api.send_message(
                    chat.get("id"),
                    "🔒 این بات قبلاً صاحب دارد. برای انتقال، کلید ADMIN_TG_ID را در .env بگذارید.")
                return

            # ---------- پنل ادمین ----------
            if self.admin is None:
                return
            reply = await self.admin.handle("tgbot", chat.get("id"), uid, text, m)
            if reply:
                await self.api.send_message(chat.get("id"), reply)
        except Exception:
            log.exception("خطا در پردازش آپدیت بات مدیریت")
