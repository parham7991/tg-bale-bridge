"""لایهٔ HTTP نازک — هندلرها فقط ترجمه می‌کنند: HTTP ⇄ موتورها.

هیچ منطق دامنه‌ای اینجا نیست؛ هر هندلر = parse → engine call → JSON.
میدلور: خطاها (DashboardError→کد، بقیه→500) · CSRF · احراز هویت سشن.
"""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from .auth import AuthEngine, AuthError
from .engines import DashboardError

log = logging.getLogger("dashboard.api")

COOKIE = "dash_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "XMLHttpRequest"


def _dash(app: web.Application):
    return app["dash"]


def json_ok(**data) -> web.Response:
    return web.json_response({"ok": True, **data})


def json_err(msg: str, status: int) -> web.Response:
    return web.json_response({"ok": False, "error": msg}, status=status)


# ───────────────────────────── میدلورها ─────────────────────────────

@web.middleware
async def error_mw(request: web.Request, handler):
    """خطای دامنه → کد HTTP؛ خطای پیش‌بینی‌نشده → 500 + لاگ."""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (DashboardError, AuthError) as e:
        return json_err(str(e), getattr(e, "status", 400))
    except Exception as e:
        log.exception("dashboard error")
        return json_err(str(e)[:200], 500)


@web.middleware
async def security_mw(request: web.Request, handler):
    dash = _dash(request.app)
    auth: AuthEngine = dash.auth
    # CSRF: هر تغییر حالت باید از فرانت خودی بیاید
    if (request.method in ("POST", "PATCH", "DELETE")
            and request.path != "/api/login"
            and request.headers.get(CSRF_HEADER) != CSRF_VALUE):
        return json_err("CSRF", 403)
    # احراز هویت: همهٔ /api به‌جز login
    if request.path.startswith("/api") and request.path != "/api/login":
        token = request.cookies.get(COOKIE, "")
        if not auth.is_valid(token):
            return json_err("unauthorized", 401)
        request["session"] = token
    return await handler(request)


# ───────────────────────────── هندلرها ─────────────────────────────

async def index(request: web.Request) -> web.Response:
    html = (Path(__file__).parent / "dash.html").read_text(encoding="utf-8")
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def login(request: web.Request) -> web.Response:
    dash = _dash(request.app)
    ip = request.remote or "?"
    if dash.auth.check_lock(ip):
        return json_err("تلاش‌های زیاد — یک دقیقه صبر کنید", 429)
    body = await request.json()
    if not dash.auth.verify(str(body.get("username", "")), str(body.get("password", ""))):
        dash.auth.register_fail(ip)
        return json_err("یوزرنیم یا رمز غلط است", 401)
    dash.auth.reset_fails(ip)
    resp = web.json_response({"ok": True, "user": dash.auth.username})
    resp.set_cookie(COOKIE, dash.auth.create_session(), httponly=True, samesite="Strict",
                    max_age=AuthEngine.SESSION_TTL, path="/")
    return resp


async def logout(request: web.Request) -> web.Response:
    dash = _dash(request.app)
    dash.auth.drop_session(request.cookies.get(COOKIE, ""))
    resp = json_ok()
    resp.del_cookie(COOKIE, path="/")
    return resp


async def change_pw(request: web.Request) -> web.Response:
    body = await request.json()
    _dash(request.app).auth.change_password(str(body.get("new", "")))
    return json_ok()


async def status(request: web.Request) -> web.Response:
    return web.json_response(_dash(request.app).status.snapshot())


async def list_pairs(request: web.Request) -> web.Response:
    return json_ok(pairs=_dash(request.app).pairs.list())


async def add_pair(request: web.Request) -> web.Response:
    body = await request.json()
    pid = await _dash(request.app).pairs.add(
        str(body.get("tg", "")), str(body.get("bale", "")), str(body.get("mode", "both")))
    return json_ok(pair_id=pid)


async def set_mode(request: web.Request) -> web.Response:
    body = await request.json()
    mode = _dash(request.app).pairs.set_mode(request.match_info["pid"], str(body.get("mode", "")))
    return json_ok(mode=mode)


async def remove_pair(request: web.Request) -> web.Response:
    _dash(request.app).pairs.remove(request.match_info["pid"])
    return json_ok()


async def pause(request: web.Request) -> web.Response:
    _dash(request.app).control.pause()
    return json_ok(paused=True)


async def resume(request: web.Request) -> web.Response:
    _dash(request.app).control.resume()
    return json_ok(paused=False)


async def logs(request: web.Request) -> web.Response:
    return json_ok(lines=_dash(request.app).logs.tail(request.query.get("n", "80")))


async def access(request: web.Request) -> web.Response:
    report = await _dash(request.app).ops.access_report()
    return json_ok(report=report)


async def promote(request: web.Request) -> web.Response:
    report = await _dash(request.app).ops.promote_bot()
    return json_ok(report=report)


def routes() -> web.RouteTableDef:
    r = web.RouteTableDef()
    r.get("/")(index)
    r.post("/api/login")(login)
    r.post("/api/logout")(logout)
    r.post("/api/passwd")(change_pw)
    r.get("/api/status")(status)
    r.get("/api/pairs")(list_pairs)
    r.post("/api/pairs")(add_pair)
    r.patch("/api/pairs/{pid}")(set_mode)
    r.delete("/api/pairs/{pid}")(remove_pair)
    r.post("/api/pause")(pause)
    r.post("/api/resume")(resume)
    r.get("/api/logs")(logs)
    r.post("/api/access")(access)
    r.post("/api/promote")(promote)
    return r
