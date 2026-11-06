"""Service d'aiguillage TRN : pages publiques, intégrations et côté privé."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
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
from . import events as ev
from .auth import AuthError, DiscordOAuth, PasswordLogin, new_token, tokens_match
from .config import Config
from .dispatch import RequestService
from .events import EventLog
from .extension import ExtensionAuthError, ExtensionVerifier
from .modauth import COOKIE_NAME, ModAuth
from .store import Status, Store, clean_source
from .twitch_api import BOT_SCOPES, MOD_SCOPES, TwitchClient, TwitchError

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
SESSION_HOURS = 12
DURATION_CHOICES = (1, 2, 4, 8, 12)


def create_app(
    config: Config,
    store: Store | None = None,
    *,
    twitch: TwitchClient | None = None,
    events: EventLog | None = None,
    start_bots: bool = True,
) -> FastAPI:
    """Assemble le service. `twitch` et `events` sont injectables pour les tests."""
    store = store or Store(config.database_path)
    events = events or EventLog(store, config.sheets_webhook_url, config.sheets_webhook_secret)
    service = RequestService(store, events, config.request_cooldown_minutes)
    if twitch is None and config.twitch_enabled:
        twitch = TwitchClient(config.twitch_client_id or "", config.twitch_client_secret or "")
    modauth = ModAuth(twitch, config.secret_key, config.mod_session_days) if twitch else None
    extension = (
        ExtensionVerifier(config.extension_client_id or "", config.extension_secret or "")
        if config.extension_enabled else None
    )

    chat_bot = None
    if twitch is not None:
        from .twitch_bot import TwitchChatBot

        chat_bot = TwitchChatBot(
            config.twitch_client_id or "", config.twitch_client_secret or "",
            store, service, events, config.secret_key,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        events.start()
        discord_task = None
        if start_bots and chat_bot is not None:
            try:
                await chat_bot.start()
            except Exception:
                log.exception("Démarrage du bot Twitch impossible")
        if start_bots and config.discord_bot_enabled:
            import asyncio

            from .discord_bot import TrnBot, run_until_closed

            bot = TrnBot(config, store, service, events, twitch, chat_bot)
            app.state.discord_bot = bot
            discord_task = asyncio.create_task(run_until_closed(bot, config.discord_bot_token or ""))
        yield
        if discord_task is not None:
            await app.state.discord_bot.close()
            await discord_task
        if chat_bot is not None:
            await chat_bot.stop()
        await events.stop()

    app = FastAPI(title="Accès TRN", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.config = config
    app.state.store = store
    app.state.events = events
    app.state.service = service
    app.state.twitch = twitch
    app.state.modauth = modauth
    app.state.chat_bot = chat_bot
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
        path = request.url.path
        embeddable = path in ("/widget", "/badge.svg", "/qr.svg")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "base-uri 'none'; form-action 'self' https://discord.com; "
            f"frame-ancestors {'*' if embeddable else 'none'}"
        )
        if path.startswith(("/admin", "/c/", "/auth/", "/bot/", "/ext/")):
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
        events.record(ev.STATUT_CHANGE, source="web", actor=user["name"],
                      message=message.strip()[:200], trn_status=new_status.value)
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

    # ------------------------------------------------------- option 2 : page de la chaîne

    def channel_render(request: Request, login: str, ctx: dict, status_code: int = 200,
                       cookie: str | None = None):
        response = templates.TemplateResponse(request, "channel.html", ctx, status_code=status_code)
        if cookie is not None:
            set_mod_cookie(response, cookie)
        return response

    def set_mod_cookie(response: Response, value: str) -> None:
        response.set_cookie(
            COOKIE_NAME, value, max_age=config.mod_session_days * 86400, httponly=True,
            secure=config.secure_cookies, samesite="lax", path="/",
        )

    async def channel_context(request: Request, login: str) -> tuple[dict, str | None, object]:
        """Contexte de la page /c/<login>, avec vérification EN DIRECT du statut de mod."""
        channel = store.get_channel(login)
        ctx = status_context(login if channel else None)
        ctx.update(channel=channel, login=clean_source(login), csrf=csrf_token(request),
                   mod_state="anonymous", mod_user=None, result=None, twitch_enabled=modauth is not None)
        new_cookie, check = None, None
        if channel is None:
            ctx["mod_state"] = "unknown_channel"
        elif modauth is not None and request.cookies.get(COOKIE_NAME):
            try:
                check = await modauth.check(request.cookies.get(COOKIE_NAME), channel)
            except TwitchError:
                log.exception("Vérification Twitch impossible")
                ctx["mod_state"] = "twitch_error"
            else:
                if check is None:
                    ctx["mod_state"] = "expired"
                else:
                    ctx["mod_user"] = check.user
                    ctx["mod_state"] = "mod" if check.is_mod else "not_mod"
                    new_cookie = check.cookie_value
        return ctx, new_cookie, check

    @app.get("/c/{login}", response_class=HTMLResponse)
    async def channel_page(request: Request, login: str):
        ctx, cookie, _ = await channel_context(request, login)
        if ctx["channel"] is not None:
            store.count("page_chaine", login)
        return channel_render(request, login, ctx, cookie=cookie)

    @app.post("/c/{login}/demande", response_class=HTMLResponse)
    async def channel_request(request: Request, login: str, csrf: str = Form(""), message: str = Form("")):
        ctx, cookie, check = await channel_context(request, login)
        if not tokens_match(request.session.get("csrf"), csrf):
            ctx["error"] = "Le formulaire a expiré. Recharge la page et réessaie."
            return channel_render(request, login, ctx, 400, cookie)
        if ctx["mod_state"] != "mod" or check is None:
            if ctx["channel"] is not None and check is not None:
                events.record(ev.DEMANDE_REFUSEE, channel=ctx["channel"].login, source="page",
                              actor=check.user.login, detail="pas modérateur·rice de la chaîne")
            ctx["error"] = "Seuls le streamer et les mods de cette chaîne peuvent faire une demande."
            return channel_render(request, login, ctx, 403, cookie)
        result = await service.submit(ctx["channel"].login, source="page",
                                      requested_by=check.user.login, message=message)
        ctx["result"] = texts.request_result_text(result.outcome.value, result.trn_status,
                                                  result.retry_after_minutes)
        ctx["result_ok"] = result.outcome.value == "envoyee"
        return channel_render(request, login, ctx, cookie=cookie)

    # ------------------------------------------------------- connexion Twitch (mods, bot)

    def twitch_redirect(request: Request, purpose: str, scopes: tuple[str, ...], next_url: str,
                        force_verify: bool = False):
        state = new_token()
        request.session["twitch_oauth"] = {"state": state, "purpose": purpose, "next": next_url}
        return RedirectResponse(
            twitch.authorize_url(config.twitch_redirect_uri, scopes, state, force_verify),  # type: ignore[union-attr]
            status_code=303,
        )

    @app.get("/auth/twitch/login")
    async def twitch_login(request: Request, chaine: str = ""):
        if twitch is None:
            return PlainTextResponse("Connexion Twitch non configurée.", status_code=404)
        return twitch_redirect(request, "mod", MOD_SCOPES, f"/c/{clean_source(chaine)}")

    @app.get("/bot/autoriser")
    async def bot_authorize(request: Request, cle: str = ""):
        if twitch is None or not config.bot_setup_key or not hmac.compare_digest(cle, config.bot_setup_key):
            return PlainTextResponse("Introuvable.", status_code=404)
        return twitch_redirect(request, "bot", BOT_SCOPES, "/", force_verify=True)

    @app.get("/auth/twitch/callback")
    async def twitch_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        pending = request.session.pop("twitch_oauth", None) or {}
        if twitch is None or error or not code or not tokens_match(pending.get("state"), state):
            return message_page(request, "Connexion annulée ou expirée",
                                "La connexion à Twitch n'a pas abouti. Retourne à la page précédente et réessaie.", 400)
        try:
            tokens = await twitch.exchange_code(code, config.twitch_redirect_uri)
            user = await twitch.get_me(tokens.access_token)
        except TwitchError:
            log.exception("Échange de code Twitch")
            return message_page(request, "Erreur Twitch", "Twitch n'a pas répondu correctement. Réessaie.", 502)
        if pending.get("purpose") == "bot":
            await chat_bot.authorize(tokens, user.login)  # type: ignore[union-attr]
            return message_page(
                request, "Bot Twitch autorisé",
                f"Le bot est maintenant connecté avec le compte « {user.login} ». "
                f"Il écoute {len(store.list_channels())} chaîne(s) inscrite(s). "
                f"Chaque streamer doit taper /mod {user.login} dans son chat.",
            )
        response = RedirectResponse(pending.get("next") or "/", status_code=303)
        set_mod_cookie(response, modauth.make_cookie(user, tokens))  # type: ignore[union-attr]
        return response

    @app.post("/auth/twitch/logout")
    async def twitch_logout(request: Request, csrf: str = Form(""), chaine: str = Form("")):
        response = RedirectResponse(f"/c/{clean_source(chaine)}" if chaine else "/", status_code=303)
        if tokens_match(request.session.get("csrf"), csrf):
            response.delete_cookie(COOKIE_NAME, path="/")
        return response

    def message_page(request: Request, title: str, text: str, status_code: int = 200):
        return templates.TemplateResponse(request, "message.html", {"title": title, "text": text},
                                          status_code=status_code)

    # ------------------------------------------------------- option 3 : extension Twitch

    def ext_headers() -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": extension.origin if extension else "null",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }

    @app.options("/ext/{path:path}")
    async def ext_preflight(path: str):
        if extension is None:
            return Response(status_code=404)
        return Response(status_code=204, headers=ext_headers())

    def ext_viewer(request: Request):
        if extension is None:
            return None, JSONResponse({"error": "extension non configurée"}, 404)
        try:
            return extension.verify(request.headers.get("authorization")), None
        except ExtensionAuthError:
            return None, JSONResponse({"error": "jeton invalide"}, 401, headers=ext_headers())

    @app.get("/ext/info")
    async def ext_info(request: Request):
        viewer, error = ext_viewer(request)
        if error:
            return error
        channel = store.get_channel_by_id(viewer.channel_id)
        current = store.current()
        t = texts.STATUS_TEXTS[current.status]
        return JSONResponse(
            {
                "status": current.status.value, "label": t.label, "emoji": t.emoji,
                "headline": t.headline, "message": current.message, "url": config.base_url,
                "registered": channel is not None,
                "can_request": viewer.can_request and channel is not None,
            },
            headers=ext_headers(),
        )

    @app.post("/ext/demande")
    async def ext_request(request: Request):
        viewer, error = ext_viewer(request)
        if error:
            return error
        channel = store.get_channel_by_id(viewer.channel_id)
        if not viewer.can_request or channel is None:
            events.record(ev.DEMANDE_REFUSEE, channel=channel.login if channel else viewer.channel_id,
                          source="extension", actor=viewer.role, detail="rôle ou chaîne non autorisé")
            return JSONResponse({"error": "réservé au streamer et aux mods"}, 403, headers=ext_headers())
        try:
            body = await request.json()
        except ValueError:
            body = {}
        message = str(body.get("message", ""))[:300] if isinstance(body, dict) else ""
        requested_by = await extension_requester(viewer, channel)
        result = await service.submit(channel.login, source="extension", requested_by=requested_by,
                                      message=message)
        return JSONResponse(
            {"outcome": result.outcome.value,
             "text": texts.request_result_text(result.outcome.value, result.trn_status,
                                               result.retry_after_minutes)},
            headers=ext_headers(),
        )

    async def extension_requester(viewer, channel) -> str:
        if viewer.role == "broadcaster":
            return channel.login
        if viewer.user_id and twitch is not None:
            try:
                user = await twitch.get_user_by_id(viewer.user_id)
                if user:
                    return user.login
            except TwitchError:
                log.warning("Pseudo du mod introuvable (extension)")
        return "mod (identité non partagée)"

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
