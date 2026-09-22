"""داشبورد وب — مدیریت کامل پل تلگرام ⇄ بله از مرورگر.

بک‌اند: aiohttp (بدون وابستگی جدید) · احراز هویت: PBKDF2 + توکن سشن کوکی HttpOnly
· ضد-CSRF با هدر X-Requested-With · محدودیت تلاش ورود.

یوزرنیم/رمز از داخل بات تلگرام ست می‌شود (/dashboard رمز اولیه می‌سازد،
/passwd و /dashuser عوض می‌کنند) — و از خود داشبورد هم می‌شود رمز را عوض کرد.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from pathlib import Path

from aiohttp import web

from .admin import MODE_ALIASES
from .bot_api import BotAPI
from .store import Store

log = logging.getLogger("dashboard")

COOKIE = "dash_session"
VERSION = "2.2.0"
PBKDF_ITERS = 100_000
MAX_FAILS = 5
LOCK_SECONDS = 60


def _hash(password: str, salt_hex: str, iters: int = PBKDF_ITERS) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iters
    ).hex()


class Dashboard:
    """سرور وب داشبورد — روی همان event-loop پل اجرا می‌شود."""

    def __init__(self, db, store: Store, cfg, rt: dict | None = None) -> None:
        self.db = db
        self.store = store
        self.cfg = cfg
        # rt: {"admin","bridge","tg","bale","tg_me","bale_me","tgbot_me","log_buffer","started_at"}
        self.rt = rt or {}
        self._sessions: set[str] = set()
        self._fails: dict[str, list] = {}  # ip -> [count, lock_until]
        self._runner: web.AppRunner | None = None
        self.app = web.Application(middlewares=[self._auth_mw])
        self._routes()

    # ──────────────────────────── اعتبارنامه ────────────────────────────
    @staticmethod
    def _auth_record(store: Store) -> dict | None:
        return store.get("dash_auth")

    @classmethod
    def ensure_credentials(cls, store: Store) -> tuple[str, str | None, bool]:
        """یوزرنیم + (رمز فقط اگر تازه ساخته شد) — ساخت خودکار اولین بار."""
        rec = cls._auth_record(store)
        if rec:
            return rec.get("user", "admin"), None, False
        user, password = "admin", secrets.token_urlsafe(6)
        cls.set_credentials(store, user, password)
        return user, password, True

    @classmethod
    def set_credentials(cls, store: Store, user: str, password: str) -> None:
        salt = secrets.token_hex(16)
        store.set("dash_auth", {
            "user": user, "salt": salt,
            "hash": _hash(password, salt), "iters": PBKDF_ITERS,
        })

    @classmethod
    def change_password(cls, store: Store, new: str) -> None:
        rec = cls._auth_record(store) or {}
        cls.set_credentials(store, rec.get("user", "admin"), new)

    @classmethod
    def change_user(cls, store: Store, user: str) -> None:
        rec = cls._auth_record(store)
        if not rec:
            cls.ensure_credentials(store)
            rec = cls._auth_record(store)
        rec["user"] = user
        store.set("dash_auth", rec)

    def _verify(self, user: str, password: str) -> bool:
        rec = self._auth_record(self.store)
        if not rec or user != rec.get("user"):
            return False
        return secrets.compare_digest(_hash(password, rec["salt"], rec.get("iters", PBKDF_ITERS)),
                                      rec.get("hash", ""))

    # ──────────────────────────── مسیرها ────────────────────────────
    def _routes(self) -> None:
        r = self.app.router
        r.add_get("/", self.index)
        r.add_post("/api/login", self.login)
        r.add_post("/api/logout", self.logout)
        r.add_get("/api/status", self.status)
        r.add_get("/api/pairs", self.list_pairs)
        r.add_post("/api/pairs", self.add_pair)
        r.add_patch("/api/pairs/{pid}", self.set_mode)
        r.add_delete("/api/pairs/{pid}", self.remove_pair)
        r.add_post("/api/pause", self.pause)
        r.add_post("/api/resume", self.resume)
        r.add_get("/api/logs", self.logs)
        r.add_post("/api/access", self.access)
        r.add_post("/api/promote", self.promote)
        r.add_post("/api/passwd", self.change_pw)

    @web.middleware
    async def _auth_mw(self, request: web.Request, handler):
        # CSRF: هر تغییر حالت باید با هدر X-Requested-With بیاید
        if (request.method in ("POST", "PATCH", "DELETE")
                and request.path != "/api/login"
                and request.headers.get("X-Requested-With") != "XMLHttpRequest"):
            return web.json_response({"ok": False, "error": "CSRF"}, status=403)
        if request.path.startswith("/api") and request.path != "/api/login":
            token = request.cookies.get(COOKIE, "")
            if token not in self._sessions:
                return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            log.exception("dashboard error")
            return web.json_response({"ok": False, "error": str(e)[:200]}, status=500)

    def _locked(self, ip: str) -> bool:
        fails, until = self._fails.get(ip, [0, 0])
        return fails >= MAX_FAILS and time.time() < until

    def _register_fail(self, ip: str) -> None:
        fails, until = self._fails.get(ip, [0, 0])
        if fails + 1 >= MAX_FAILS:
            self._fails[ip] = [MAX_FAILS, time.time() + LOCK_SECONDS]
        else:
            self._fails[ip] = [fails + 1, until]

    # ──────────────────────────── هندلرها ────────────────────────────
    async def index(self, request: web.Request) -> web.Response:
        html = (Path(__file__).with_name("dash.html")).read_text(encoding="utf-8")
        return web.Response(text=html, content_type="text/html", charset="utf-8")

    async def login(self, request: web.Request) -> web.Response:
        ip = request.remote or "?"
        if self._locked(ip):
            return web.json_response(
                {"ok": False, "error": "تلاش‌های زیاد — یک دقیقه صبر کنید"}, status=429)
        body = await request.json()
        if not self._verify(str(body.get("username", "")), str(body.get("password", ""))):
            self._register_fail(ip)
            return web.json_response({"ok": False, "error": "یوزرنیم یا رمز غلط است"}, status=401)
        self._fails.pop(ip, None)
        token = secrets.token_urlsafe(32)
        self._sessions.add(token)
        resp = web.json_response({"ok": True, "user": self._auth_record(self.store).get("user")})
        resp.set_cookie(COOKIE, token, httponly=True, samesite="Strict",
                        max_age=7 * 24 * 3600, path="/")
        return resp

    async def logout(self, request: web.Request) -> web.Response:
        self._sessions.discard(request.cookies.get(COOKIE, ""))
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE, path="/")
        return resp

    async def change_pw(self, request: web.Request) -> web.Response:
        body = await request.json()
        new = str(body.get("new", ""))
        if len(new) < 6:
            return web.json_response({"ok": False, "error": "رمز حداقل ۶ کاراکتر"}, status=400)
        Dashboard.change_password(self.store, new)
        return web.json_response({"ok": True})

    # ------------------------------------------------------------ وضعیت
    async def status(self, request: web.Request) -> web.Response:
        bridge = self.rt.get("bridge")
        stats = self.db.stats()
        started = self.rt.get("started_at") or time.time()
        out = {
            "ok": True,
            "mode": "bridge" if bridge is not None else "installer",
            "version": VERSION,
            "paused": bool(getattr(bridge, "paused", False)),
            "uptime_s": int(time.time() - started),
            "pairs": stats.get("pairs", 0),
            "mapped": stats.get("mapped", 0),
            "dash_user": (self._auth_record(self.store) or {}).get("user", "admin"),
            "bale_mode": getattr(self.cfg, "BALE_MODE", "bot"),
            "accounts": {
                "tg_self": self.rt.get("tg_me") or {},
                "bale": self.rt.get("bale_me") or {},
                "bale_bot": self.rt.get("tgbot_me") or {},
                "control_bot": (self.rt.get("tgbot_me") or {}),
            },
        }
        # حذف توکن‌های حساس اگر نوشته شده باشند
        for acc in out["accounts"].values():
            acc.pop("token", None)
        return web.json_response(out)

    # ------------------------------------------------------------ جفت‌ها
    async def list_pairs(self, request: web.Request) -> web.Response:
        pairs = [dict(p) for p in self.db.list_pairs()]
        return web.json_response({"ok": True, "pairs": pairs})

    async def add_pair(self, request: web.Request) -> web.Response:
        admin = self.rt.get("admin")
        if admin is None:
            return web.json_response(
                {"ok": False, "error": "نصب ناقص است — اول ویزارد بات را کامل کنید"}, status=409)
        body = await request.json()
        mode = MODE_ALIASES.get(str(body.get("mode", "both")).lower().replace("-", "_"))
        if not mode:
            return web.json_response({"ok": False, "error": "حالت نامعتبر"}, status=400)
        tg_ref, bale_ref = str(body.get("tg", "")).strip(), str(body.get("bale", "")).strip()
        if not tg_ref or not bale_ref:
            return web.json_response({"ok": False, "error": "هر دو کانال لازم است"}, status=400)
        tg_id, tg_label, tg_user = await admin._resolve_tg(tg_ref)
        bale_id, bale_label, bale_user = await admin._resolve_bale(bale_ref)
        pid = self.db.add_pair(tg_id, tg_label, tg_user, bale_id, bale_label, bale_user, mode)
        return web.json_response({"ok": True, "pair_id": pid})

    async def set_mode(self, request: web.Request) -> web.Response:
        pid = int(request.match_info["pid"])
        body = await request.json()
        mode = MODE_ALIASES.get(str(body.get("mode", "")).lower().replace("-", "_"))
        if not mode:
            return web.json_response({"ok": False, "error": "حالت نامعتبر"}, status=400)
        if not self.db.set_mode(pid, mode):
            return web.json_response({"ok": False, "error": "جفت پیدا نشد"}, status=404)
        return web.json_response({"ok": True, "mode": mode})

    async def remove_pair(self, request: web.Request) -> web.Response:
        pid = int(request.match_info["pid"])
        ok = self.db.remove_pair(pid)
        return web.json_response({"ok": bool(ok)}, status=200 if ok else 404)

    # ------------------------------------------------------------ کنترل
    async def pause(self, request: web.Request) -> web.Response:
        bridge = self.rt.get("bridge")
        if bridge is None:
            return web.json_response({"ok": False, "error": "پل کامل نیست"}, status=409)
        bridge.paused = True
        self.db.set_meta("paused", "1")
        return web.json_response({"ok": True, "paused": True})

    async def resume(self, request: web.Request) -> web.Response:
        bridge = self.rt.get("bridge")
        if bridge is None:
            return web.json_response({"ok": False, "error": "پل کامل نیست"}, status=409)
        bridge.paused = False
        self.db.set_meta("paused", "0")
        return web.json_response({"ok": True, "paused": False})

    async def logs(self, request: web.Request) -> web.Response:
        try:
            n = max(1, min(int(request.query.get("n", "80")), 300))
        except ValueError:
            n = 80
        buf = self.rt.get("log_buffer")
        lines = buf.tail(n) if buf is not None and hasattr(buf, "tail") else []
        return web.json_response({"ok": True, "lines": lines})

    # ------------------------------------------------------------ ادمین‌ها
    async def access(self, request: web.Request) -> web.Response:
        from .wizard import probe_bale_access, probe_tg_access

        pairs = self.db.list_pairs()
        if not pairs:
            return web.json_response({"ok": False, "error": "جفتی نیست"}, status=404)
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        tg, bale = self.rt.get("tg"), self.rt.get("bale")
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            if tg is not None:
                try:
                    _, note = await probe_tg_access(tg, p["tg_chat_id"])
                except Exception as e:
                    note = f"✘ {str(e)[:60]}"
                lines.append(f"  ▫️ سلف تلگرام → {p['tg_label'] or p['tg_chat_id']}: {note}")
            if bale is not None:
                try:
                    _, note = await probe_bale_access(bale, p["bale_chat_id"])
                except Exception as e:
                    note = f"✘ {str(e)[:60]}"
                lines.append(f"  ▫️ سمت بله → {p['bale_label'] or p['bale_chat_id']}: {note}")
        return web.json_response({"ok": True, "report": "\n".join(lines)})

    async def promote(self, request: web.Request) -> web.Response:
        from .bale_user import BaleUserAPI
        from .wizard import probe_bale_access

        bale = self.rt.get("bale")
        if not isinstance(bale, BaleUserAPI):
            return web.json_response(
                {"ok": False,
                 "error": "این کار با سلف بله انجام می‌شود (BALE_MODE=user)"}, status=409)
        bb = self.store.bale_bot()
        if not bb:
            return web.json_response({"ok": False, "error": "ربات بله ثبت نشده"}, status=409)
        me = bb.get("me") or {}
        bot_ref = me.get("username") or me.get("id")
        bot_api = BotAPI(bb["token"], getattr(self.cfg, "BALE_API_BASE", "https://tapi.bale.ai"))
        lines = ["🛡 نتیجهٔ ادمین‌کردن ربات بله:"]
        for p in self.db.list_pairs():
            label = p["bale_label"] or p["bale_chat_id"]
            try:
                await bale.add_admin(p["bale_chat_id"], bot_ref)
                note = "✔ اضافه و ادمین شد"
                try:
                    ok, pnote = await probe_bale_access(bot_api, p["bale_chat_id"])
                    note += " — تست ارسال: " + ("✔" if ok else f"✘ {pnote}")
                except Exception as e:
                    note += f" — تست: ✘ {str(e)[:60]}"
            except Exception as e:
                note = f"✘ {str(e)[:120]}"
            lines.append(f"  ▫️ {label}: {note}")
        try:
            await bot_api.close()
        except Exception:
            pass
        return web.json_response({"ok": True, "report": "\n".join(lines)})

    # ──────────────────────────── چرخهٔ کار ────────────────────────────
    async def start(self) -> None:
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, getattr(self.cfg, "DASH_HOST", "0.0.0.0"),
                           int(getattr(self.cfg, "DASH_PORT", 8080)))
        await site.start()
        log.info("🌐 داشبورد: http://%s:%s (یوزرنیم/رمز: با /dashboard در بات بگیرید)",
                 getattr(self.cfg, "DASH_HOST", "0.0.0.0"), getattr(self.cfg, "DASH_PORT", 8080))

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
