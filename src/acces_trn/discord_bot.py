"""Bot Discord du serveur des TRN.

- Panneau de statut : un message avec 3 boutons (🟢 / 🟡 / 🔴). Un clic suffit.
- Salon des demandes : chaque demande d'une chaîne y apparaît, avec « Je m'en occupe ».
- /chaine ajouter|retirer|liste : gestion des chaînes inscrites (pilote).
Seules les personnes ayant le rôle TRN (DISCORD_ROLE_ID) peuvent utiliser les boutons et commandes.
"""

from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import events as ev
from . import texts
from .config import Config
from .dispatch import RequestService
from .events import EventLog
from .store import HelpRequest, Status, Store
from .twitch_api import TwitchClient, TwitchError

log = logging.getLogger(__name__)

PANEL_SECRET = "discord_status_panel"  # « channel_id:message_id » du panneau
SOURCE_LABELS = {"chat": "commande !trn", "page": "page Web", "extension": "extension Twitch"}
STATUS_COLORS = {
    Status.AVAILABLE: discord.Color.green(),
    Status.BUSY: discord.Color.gold(),
    Status.OFFLINE: discord.Color.red(),
}


def _local(dt: datetime, config: Config) -> str:
    return dt.astimezone(config.timezone).strftime("%H h %M")


def build_status_embed(store: Store, config: Config) -> discord.Embed:
    cur = store.current()
    t = texts.STATUS_TEXTS[cur.status]
    embed = discord.Embed(title=f"{t.emoji} {t.label}", color=STATUS_COLORS[cur.status])
    lines = []
    if cur.status is not Status.OFFLINE and cur.expires_at:
        lines.append(f"Retour automatique à « hors ligne » à **{_local(cur.expires_at, config)}**.")
    if cur.expired:
        lines.append("Le dernier statut est arrivé à échéance.")
    if cur.message:
        lines.append(f"Message public : « {cur.message} »")
    if cur.set_by:
        lines.append(f"Dernier changement : {cur.set_by}, à {_local(cur.set_at, config)}.")
    lines.append(f"\nCliquer sur un bouton change le statut pour {config.default_duration_hours} h.")
    embed.description = "\n".join(lines)
    return embed


def build_request_embed(request: HelpRequest, config: Config) -> discord.Embed:
    sent = request.outcome == "envoyee"
    title = f"📣 Demande de la chaîne {request.channel}"
    if not sent:
        title += " (aucun TRN en service)"
    embed = discord.Embed(
        title=title,
        url=f"https://twitch.tv/{request.channel}",
        color=discord.Color.green() if request.claimed_by else (
            discord.Color.orange() if sent else discord.Color.dark_grey()
        ),
        timestamp=request.created_at,
    )
    embed.add_field(name="Chaîne", value=f"[twitch.tv/{request.channel}](https://twitch.tv/{request.channel})")
    embed.add_field(name="Heure", value=_local(request.created_at, config))
    embed.add_field(name="Via", value=f"{SOURCE_LABELS.get(request.source, request.source)} · {request.requested_by}")
    if request.message:
        embed.add_field(name="Message", value=request.message[:1024], inline=False)
    if request.claimed_by:
        embed.add_field(
            name="Pris en charge",
            value=f"{request.claimed_by} à {_local(request.claimed_at, config)}",  # type: ignore[arg-type]
            inline=False,
        )
    embed.set_footer(text=f"Demande #{request.id}")
    return embed


def build_request_view(request: HelpRequest) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if not request.claimed_by:
        view.add_item(ClaimButton(request.id))
    return view


def build_panel_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for status in Status:
        view.add_item(StatusButton(status))
    return view


def _has_role(bot: "TrnBot", user: discord.abc.User) -> bool:
    return isinstance(user, discord.Member) and any(
        str(r.id) == bot.config.discord_role_id for r in user.roles
    )


class StatusButton(discord.ui.DynamicItem[discord.ui.Button], template=r"statut:(?P<status>available|busy|offline)"):
    STYLES = {
        Status.AVAILABLE: discord.ButtonStyle.success,
        Status.BUSY: discord.ButtonStyle.primary,
        Status.OFFLINE: discord.ButtonStyle.danger,
    }

    def __init__(self, status: Status) -> None:
        t = texts.STATUS_TEXTS[status]
        super().__init__(
            discord.ui.Button(
                label=t.label, emoji=t.emoji, style=self.STYLES[status], custom_id=f"statut:{status.value}"
            )
        )
        self.status = status

    @classmethod
    async def from_custom_id(cls, interaction, item, match):  # noqa: ANN001
        return cls(Status(match["status"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot: TrnBot = interaction.client  # type: ignore[assignment]
        if not _has_role(bot, interaction.user):
            await interaction.response.send_message("Réservé aux TRN.", ephemeral=True)
            return
        name = interaction.user.display_name
        bot.store.set_status(self.status, name, "", bot.config.default_duration_hours)
        bot.events.record(ev.STATUT_CHANGE, source="discord", actor=name, trn_status=self.status.value)
        await interaction.response.edit_message(embed=build_status_embed(bot.store, bot.config))
        bot.remember_panel_status()


class ClaimButton(discord.ui.DynamicItem[discord.ui.Button], template=r"demande:prendre:(?P<id>\d+)"):
    def __init__(self, request_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label="Je m'en occupe", style=discord.ButtonStyle.primary, custom_id=f"demande:prendre:{request_id}"
            )
        )
        self.request_id = request_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):  # noqa: ANN001
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot: TrnBot = interaction.client  # type: ignore[assignment]
        if not _has_role(bot, interaction.user):
            await interaction.response.send_message("Réservé aux TRN.", ephemeral=True)
            return
        request = bot.service.claim(self.request_id, interaction.user.display_name)
        if request is None:
            await interaction.response.send_message("Cette demande est déjà prise en charge.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=build_request_embed(request, bot.config), view=build_request_view(request)
        )


class TrnBot(commands.Bot):
    def __init__(
        self,
        config: Config,
        store: Store,
        service: RequestService,
        events: EventLog,
        twitch: TwitchClient | None,
        chat_bot=None,  # TwitchChatBot | None
    ) -> None:
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())
        self.config = config
        self.store = store
        self.service = service
        self.events = events
        self.twitch = twitch
        self.chat_bot = chat_bot
        self._guild = discord.Object(id=int(config.discord_guild_id or 0))
        self._panel_status: tuple | None = None
        service.notifier = self.notify_request

    async def setup_hook(self) -> None:
        self.add_dynamic_items(StatusButton, ClaimButton)
        register_commands(self)
        self.tree.copy_global_to(guild=self._guild)
        await self.tree.sync(guild=self._guild)
        self.refresh_panel.start()

    async def on_ready(self) -> None:
        log.info("Bot Discord connecté en tant que %s", self.user)

    async def notify_request(self, request: HelpRequest, mention: bool) -> str | None:
        await self.wait_until_ready()
        channel_id = int(self.config.discord_requests_channel_id or 0)
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        msg = await channel.send(  # type: ignore[union-attr]
            content=f"<@&{self.config.discord_role_id}>" if mention else None,
            embed=build_request_embed(request, self.config),
            view=build_request_view(request),
            allowed_mentions=discord.AllowedMentions(roles=mention),
        )
        return str(msg.id)

    def remember_panel_status(self) -> None:
        cur = self.store.current()
        self._panel_status = (cur.status, cur.set_at, cur.message, cur.expired)

    @tasks.loop(minutes=1)
    async def refresh_panel(self) -> None:
        """Met à jour le panneau quand le statut change ailleurs (échéance, page /admin)."""
        cur = self.store.current()
        state = (cur.status, cur.set_at, cur.message, cur.expired)
        if state == self._panel_status:
            return
        self._panel_status = state
        ref = self.store.get_secret(PANEL_SECRET)
        if not ref:
            return
        channel_id, message_id = (int(x) for x in ref.split(":"))
        try:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            msg = await channel.fetch_message(message_id)  # type: ignore[union-attr]
            await msg.edit(embed=build_status_embed(self.store, self.config), view=build_panel_view())
        except discord.HTTPException:
            log.warning("Panneau de statut introuvable ; republier avec /panneau-statut")

    @refresh_panel.before_loop
    async def _before_refresh(self) -> None:
        await self.wait_until_ready()


def register_commands(bot: TrnBot) -> None:
    tree = bot.tree

    async def ensure_trn(interaction: discord.Interaction) -> bool:
        if _has_role(bot, interaction.user):
            return True
        await interaction.response.send_message("Réservé aux TRN.", ephemeral=True)
        return False

    @tree.command(name="panneau-statut", description="Publier le panneau de statut des TRN dans ce salon")
    async def panneau(interaction: discord.Interaction) -> None:
        if not await ensure_trn(interaction):
            return
        msg = await interaction.channel.send(  # type: ignore[union-attr]
            embed=build_status_embed(bot.store, bot.config), view=build_panel_view()
        )
        bot.store.set_secret(PANEL_SECRET, f"{msg.channel.id}:{msg.id}")
        bot.remember_panel_status()
        await interaction.response.send_message(
            "Panneau publié. Pense à l'épingler. L'ancien panneau, s'il y en avait un, n'est plus mis à jour.",
            ephemeral=True,
        )

    @tree.command(name="statut", description="Voir le statut actuel des TRN")
    async def statut(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_status_embed(bot.store, bot.config), ephemeral=True)

    chaine = app_commands.Group(name="chaine", description="Chaînes Twitch inscrites auprès des TRN")

    @chaine.command(name="ajouter", description="Inscrire une chaîne Twitch")
    @app_commands.describe(nom="Nom de la chaîne Twitch (ex. : machaine)")
    async def ajouter(interaction: discord.Interaction, nom: str) -> None:
        if not await ensure_trn(interaction):
            return
        if bot.twitch is None:
            await interaction.response.send_message("Twitch n'est pas configuré (TWITCH_CLIENT_ID).", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            user = await bot.twitch.get_user_by_login(nom)
        except TwitchError as exc:
            await interaction.followup.send(f"Erreur Twitch : {exc}", ephemeral=True)
            return
        if user is None:
            await interaction.followup.send(f"Aucune chaîne Twitch nommée « {nom} ».", ephemeral=True)
            return
        channel = bot.store.add_channel(user.login, user.id, user.display_name, interaction.user.display_name)
        bot.events.record(ev.CHAINE_AJOUTEE, channel=channel.login, source="discord", actor=interaction.user.display_name)
        if bot.chat_bot is not None:
            await bot.chat_bot.add_channel(channel)
        base = bot.config.base_url
        bot_line = (
            f"\n• Commande chat : le streamer tape `/mod {bot.chat_bot.bot_login}` une fois."
            if bot.chat_bot is not None and bot.chat_bot.bot_login else ""
        )
        await interaction.followup.send(
            f"✅ **{channel.display_name}** est inscrite.\n"
            f"• Lien pour les mods : {base}/c/{channel.login}{bot_line}\n"
            f"• Trousse : {base}/trousse?src={channel.login}",
            ephemeral=True,
        )

    @chaine.command(name="retirer", description="Retirer une chaîne")
    async def retirer(interaction: discord.Interaction, nom: str) -> None:
        if not await ensure_trn(interaction):
            return
        login = nom.lower().lstrip("@")
        if not bot.store.remove_channel(login):
            await interaction.response.send_message(f"« {login} » n'est pas inscrite.", ephemeral=True)
            return
        bot.events.record(ev.CHAINE_RETIREE, channel=login, source="discord", actor=interaction.user.display_name)
        if bot.chat_bot is not None:
            await bot.chat_bot.remove_channel(login)
        await interaction.response.send_message(f"Chaîne « {login} » retirée.", ephemeral=True)

    @chaine.command(name="liste", description="Voir les chaînes inscrites")
    async def liste(interaction: discord.Interaction) -> None:
        if not await ensure_trn(interaction):
            return
        channels = bot.store.list_channels()
        text = "\n".join(f"• {c.display_name} — {bot.config.base_url}/c/{c.login}" for c in channels)
        await interaction.response.send_message(text or "Aucune chaîne inscrite.", ephemeral=True)

    tree.add_command(chaine)


async def run_until_closed(bot: TrnBot, token: str) -> None:
    try:
        await bot.start(token)
    except Exception:
        log.exception("Le bot Discord s'est arrêté")
    finally:
        if not bot.is_closed():
            await bot.close()
