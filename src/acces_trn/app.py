"""Service d'aiguillage TRN : pages publiques, intégrations et côté privé."""

from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import segno
from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import texts
from .auth import AuthError, DiscordOAuth, PasswordLogin, new_token, tokens_match
from .config import Config
from .store import Status, Store, clean_source

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
SESSION_HOURS = 12
DURATION_CHOICES = (1, 2, 4, 8, 12)


def create_app(config: Config, store: Store | None = None) -> FastAPI:
    store = store or Store(config.database_path)
    app = FastAPI(title="Accès TRN", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.store = store
    app.state.discord = DiscordOAuth(config) if config.auth_mode == "discord" else None
    app.state.password = (
        PasswordLogin(config.admin_password or "") if config.auth_mode == "password" else None
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie="trn_session",
        max_age=SESSION_HOURS * 3600,
        same_site="lax",
        https_only=config.secure_cookies,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        embeddable = request.url.path in ("/widget", "/badge.svg", "/qr.svg")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "base-uri 'none'; form-action 'self' https://discord.com; "
            f"frame-ancestors {'*' if embeddable else 'none'}"
        )
        if request.url.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals.update(org_name=config.org_name, base_url=config.base_url)

    def status_context(src: str | None = None) -> dict:
        current = store.current()
        query = f"?{urlencode({'src': clean_source(src)})}" if src else ""
        return {
            "current": current,
            "t": texts.STATUS_TEXTS[current.status],
            "status": current.status.value,
            "go_url": f"/go{query}",
            "resources": texts.EMERGENCY_RESOURCES,
            "hours_text": config.hours_text,
        }

    # ------------------------------------------------------------------ public

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, src: str | None = None):
        store.count("page", src)
        return templates.TemplateResponse(request, "index.html", status_context(src))

    @app.get("/go")
    async def go(src: str | None = None):
        store.count("go", src)
        return RedirectResponse(
            config.destination_url, status_code=302, headers={"Cache-Control": "no-store"}
        )

    @app.get("/status.json")
    async def status_json():
        current = store.current()
        t = texts.STATUS_TEXTS[current.status]
        return JSONResponse(
            {
                "status": current.status.value,
                "label": t.label,
                "emoji": t.emoji,
                "message": current.message,
                "action": t.action,
                "url": config.base_url,
                "updated_at": current.set_at.isoformat(),
            },
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=30"},
        )

    @app.get("/status.txt", response_class=PlainTextResponse)
    async def status_txt(src: str | None = None):
        store.count("chat", src)
        current = store.current()
        url = config.base_url + (f"/?{urlencode({'src': clean_source(src)})}" if src else "")
        return PlainTextResponse(
            texts.chat_line(current.status, current.message, url),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/widget", response_class=HTMLResponse)
    async def widget(request: Request, src: str | None = None, theme: str = "light"):
        ctx = status_context(src)
        ctx["theme"] = theme if theme in ("light", "dark", "overlay") else "light"
        return templates.TemplateResponse(request, "widget.html", ctx)

    @app.get("/badge.svg")
    async def badge():
        current = store.current()
        return Response(
            badge_svg(texts.STATUS_TEXTS[current.status]),
            media_type="image/svg+xml",
            headers={"Cache-Control": "max-age=60"},
        )

    @app.get("/qr.svg")
    async def qr(src: str | None = None):
        target = config.base_url + (f"/?{urlencode({'src': clean_source(src)})}" if src else "")
        svg = segno.make(target, error="m").svg_inline(scale=8, border=2)
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=86400"})

    @app.get("/trousse", response_class=HTMLResponse)
    async def kit(request: Request, src: str = "ma_chaine"):
        source = clean_source(src)
        return templates.TemplateResponse(request, "trousse.html", {"src": source})

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz():
        store.current()
        return "ok"

    # ------------------------------------------------------------------ privé

    def staff(request: Request) -> dict | None:
        return request.session.get("staff")

    def csrf_token(request: Request) -> str:
        if "csrf" not in request.session:
            request.session["csrf"] = new_token()
        return request.session["csrf"]

    def login_page(request: Request, error: str | None = None, code: int = 200):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"mode": config.auth_mode, "error": error, "csrf": csrf_token(request)},
            status_code=code,
        )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin(request: Request):
        user = staff(request)
        if not user:
            return RedirectResponse("/admin/login", status_code=303)
        ctx = status_context()
        ctx.update(
            user=user,
            csrf=csrf_token(request),
            durations=DURATION_CHOICES,
            default_duration=config.default_duration_hours,
            statuses=[(s.value, texts.STATUS_TEXTS[s]) for s in Status],
            status_labels={s.value: texts.STATUS_TEXTS[s].label for s in Status},
            changes=store.recent_changes(),
            totals=store.totals(),
            fmt=lambda d: format_local(d, config),
        )
        return templates.TemplateResponse(request, "admin.html", ctx)

    @app.post("/admin/status")
    async def admin_set_status(
        request: Request,
        status: str = Form(...),
        csrf: str = Form(""),
        message: str = Form(""),
        duration: int = Form(4),
    ):
        user = staff(request)
        if not user:
            return RedirectResponse("/admin/login", status_code=303)
        if not tokens_match(request.session.get("csrf"), csrf):
            return PlainTextResponse("Formulaire expiré, recharge la page.", status_code=400)
        try:
            new_status = Status(status)
        except ValueError:
            return PlainTextResponse("Statut inconnu.", status_code=400)
        if duration not in DURATION_CHOICES:
            duration = config.default_duration_hours
        store.set_status(new_status, user["name"], message, duration)
        log.info("Statut changé à %s par %s", new_status.value, user["name"])
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login(request: Request):
        if staff(request):
            return RedirectResponse("/admin", status_code=303)
        if config.auth_mode == "discord" and request.query_params.get("go") == "1":
            state = new_token()
            request.session["oauth_state"] = state
            return RedirectResponse(app.state.discord.authorize_url(state), status_code=303)
        return login_page(request)

    @app.post("/admin/login", response_class=HTMLResponse)
    async def admin_login_password(
        request: Request, password: str = Form(""), name: str = Form(""), csrf: str = Form("")
    ):
        if config.auth_mode != "password":
            return PlainTextResponse("Non disponible.", status_code=404)
        if not tokens_match(request.session.get("csrf"), csrf):
            return login_page(request, "Formulaire expiré, réessaie.", 400)
        try:
            user = app.state.password.check(password, name)
        except AuthError as exc:
            return login_page(request, str(exc), 401)
        start_session(request, user.id, user.name)
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin/callback")
    async def admin_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if config.auth_mode != "discord":
            return PlainTextResponse("Non disponible.", status_code=404)
        expected = request.session.pop("oauth_state", None)
        if error or not code or not tokens_match(expected, state):
            return login_page(request, "Connexion annulée ou expirée. Réessaie.", 400)
        try:
            user = await app.state.discord.login(code)
        except AuthError as exc:
            return login_page(request, str(exc), 403)
        start_session(request, user.id, user.name)
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/logout")
    async def admin_logout(request: Request, csrf: str = Form("")):
        if tokens_match(request.session.get("csrf"), csrf):
            request.session.clear()
        return RedirectResponse("/", status_code=303)

    def start_session(request: Request, user_id: str, name: str) -> None:
        request.session.clear()
        request.session["staff"] = {"id": user_id, "name": name}
        request.session["csrf"] = new_token()

    return app


def format_local(value: datetime | str | None, config: Config) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.astimezone(config.timezone).strftime("%Y-%m-%d %H:%M")


def badge_svg(t: texts.StatusText) -> str:
    """Badge façon « shields.io » : [ TRN | disponible ]."""
    left, right = "TRN", t.label.removeprefix("TRN ")
    lw, rw = 40, 12 + 7 * len(right)
    width = lw + rw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="22" role="img" '
        f'aria-label="{escape(t.label)}">'
        f"<title>{escape(t.label)}</title>"
        f'<rect width="{lw}" height="22" rx="4" fill="#3b3f46"/>'
        f'<rect x="{lw - 4}" width="{rw + 4}" height="22" rx="4" fill="{t.color}"/>'
        f'<rect x="{lw - 4}" width="4" height="22" fill="{t.color}"/>'
        '<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="12">'
        f'<text x="{lw / 2}" y="15" text-anchor="middle">{left}</text>'
        f'<text x="{lw + rw / 2}" y="15" text-anchor="middle">{escape(right)}</text>'
        "</g></svg>"
    )
