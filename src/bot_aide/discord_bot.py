"""Côté Discord : commandes /aide et /signaler, clic droit « Signaler ce message »,
panneau public avec boutons, et salon #signalements pour l'équipe.
"""

from __future__ import annotations

import logging
from datetime import time as dtime
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import messages
from .config import Config
from .db import Kind, Report, ReportStore, Source, Status
from .ratelimit import RateLimiter

log = logging.getLogger(__name__)

STATUS_LABELS = {
    Status.OPEN: ("🔴 Ouvert", discord.Color.red()),
    Status.CLAIMED: ("🟡 Pris en charge", discord.Color.gold()),
    Status.CLOSED: ("🟢 Fermé", discord.Color.green()),
}
KIND_LABELS = {Kind.REPORT: "Signalement", Kind.HELP: "Demande d'aide"}
SOURCE_LABELS = {Source.DISCORD: "Discord", Source.TWITCH: "Twitch"}


def _clip(text: str | None, limit: int = 1024) -> str:
    if not text:
        return "—"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_report_embed(report: Report) -> discord.Embed:
    status_label, color = STATUS_LABELS[report.status]
    embed = discord.Embed(
        title=f"{KIND_LABELS[report.kind]} #{report.id} · {SOURCE_LABELS[report.source]}",
        description=_clip(report.description, 4000),
        color=color,
        timestamp=report.created_at,
    )
    embed.add_field(name="Statut", value=status_label, inline=True)
    embed.add_field(name="Signalé par", value=_clip(report.reporter or "Anonyme"), inline=True)
    if report.claimed_by:
        embed.add_field(name="Intervenant·e", value=_clip(report.claimed_by), inline=True)
    if report.target:
        embed.add_field(name="Personne concernée", value=_clip(report.target), inline=False)
    if report.location:
        embed.add_field(name="Où", value=_clip(report.location), inline=False)
    if report.evidence:
        embed.add_field(name="Preuve / lien", value=_clip(report.evidence), inline=False)
    return embed


def build_staff_view(report: Report) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if report.status == Status.OPEN:
        view.add_item(ReportActionButton("claim", report.id))
    if report.status != Status.CLOSED:
        view.add_item(ReportActionButton("close", report.id))
    return view


def _is_staff(bot: "AideBot", member: discord.abc.User) -> bool:
    return isinstance(member, discord.Member) and any(
        r.id == bot.config.discord.staff_role_id for r in member.roles
    )


# --------------------------------------------------------------------------
# Boutons persistants (ils fonctionnent encore après un redémarrage du bot)
# --------------------------------------------------------------------------


class ReportActionButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"report:(?P<action>claim|close):(?P<id>\d+)",
):
    """Boutons « Je prends en charge » et « Fermer » sous chaque dossier."""

    STYLES = {
        "claim": ("Je prends en charge", discord.ButtonStyle.primary),
        "close": ("Fermer", discord.ButtonStyle.secondary),
    }

    def __init__(self, action: str, report_id: int) -> None:
        label, style = self.STYLES[action]
        super().__init__(
            discord.ui.Button(label=label, style=style, custom_id=f"report:{action}:{report_id}")
        )
        self.action = action
        self.report_id = report_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):  # noqa: ANN001
        return cls(match["action"], int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot: AideBot = interaction.client  # type: ignore[assignment]
        if not _is_staff(bot, interaction.user):
            await interaction.response.send_message(messages.STAFF_ONLY, ephemeral=True)
            return
        staff = interaction.user.display_name
        if self.action == "claim":
            report = bot.store.claim(self.report_id, staff)
        else:
            report = bot.store.close_report(self.report_id, staff)
        if report is None:
            await interaction.response.send_message(messages.ALREADY_HANDLED, ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=build_report_embed(report), view=build_staff_view(report)
        )


class HelpButton(discord.ui.DynamicItem[discord.ui.Button], template=r"panel:help"):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                label=messages.HELP_BUTTON_LABEL,
                style=discord.ButtonStyle.success,
                emoji="💬",
                custom_id="panel:help",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):  # noqa: ANN001
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        bot: AideBot = interaction.client  # type: ignore[assignment]
        await bot.open_help_thread(interaction)


class ReportPanelButton(discord.ui.DynamicItem[discord.ui.Button], template=r"panel:report"):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                label="Signaler un comportement",
                style=discord.ButtonStyle.danger,
                emoji="🚩",
                custom_id="panel:report",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):  # noqa: ANN001
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ReportModal())


def build_help_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(HelpButton())
    return view


def build_panel_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(HelpButton())
    view.add_item(ReportPanelButton())
    return view


# --------------------------------------------------------------------------
# Formulaire de signalement
# --------------------------------------------------------------------------


class ReportModal(discord.ui.Modal, title="Signaler un comportement"):
    def __init__(
        self,
        *,
        target: str | None = None,
        location: str | None = None,
        evidence: str | None = None,
    ) -> None:
        super().__init__()
        self.target = discord.ui.TextInput(required=False, max_length=100, default=target)
        self.location = discord.ui.TextInput(
            required=False,
            max_length=200,
            default=location,
            placeholder="Ex. : salon #général, chaîne Twitch de X",
        )
        self.description = discord.ui.TextInput(
            style=discord.TextStyle.paragraph, max_length=1500, min_length=5
        )
        self.evidence = discord.ui.TextInput(
            required=False, max_length=500, default=evidence, placeholder="Lien vers un message, un clip…"
        )
        self.anonymous = discord.ui.Checkbox()
        self.add_item(discord.ui.Label(text="Personne concernée (pseudo)", component=self.target))
        self.add_item(discord.ui.Label(text="Où ça s'est passé", component=self.location))
        self.add_item(discord.ui.Label(text="Que s'est-il passé ?", component=self.description))
        self.add_item(discord.ui.Label(text="Lien ou preuve (facultatif)", component=self.evidence))
        self.add_item(
            discord.ui.Label(
                text="Rester anonyme",
                description="L'équipe ne verra pas qui a envoyé ce signalement.",
                component=self.anonymous,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot: AideBot = interaction.client  # type: ignore[assignment]
        if not bot.limiter.allow(f"discord:{interaction.user.id}"):
            await interaction.response.send_message(messages.RATE_LIMITED, ephemeral=True)
            return
        anonymous = self.anonymous.value
        report = bot.store.create(
            source=Source.DISCORD,
            kind=Kind.REPORT,
            reporter=None if anonymous else f"{interaction.user} ({interaction.user.id})",
            target=self.target.value or None,
            location=self.location.value or None,
            description=self.description.value,
            evidence=self.evidence.value or None,
        )
        await bot.post_to_staff(report)
        template = messages.REPORT_THANKS_ANONYMOUS if anonymous else messages.REPORT_THANKS
        await interaction.response.send_message(template.format(id=report.id), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception("Erreur dans le formulaire de signalement", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Oups, une erreur est survenue. Réessaie ou écris directement à l'équipe.",
                ephemeral=True,
            )


# --------------------------------------------------------------------------
# Le bot
# --------------------------------------------------------------------------


class AideBot(commands.Bot):
    def __init__(self, config: Config, store: ReportStore) -> None:
        intents = discord.Intents.default()  # aucun intent privilégié requis
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.config = config
        self.store = store
        self.limiter = RateLimiter(config.reports_per_hour)
        self._guild = discord.Object(id=config.discord.guild_id)

    async def setup_hook(self) -> None:
        self.add_dynamic_items(ReportActionButton, HelpButton, ReportPanelButton)
        register_commands(self)
        # Synchronisation sur un seul serveur : instantanée (la globale prend jusqu'à 1 h).
        self.tree.copy_global_to(guild=self._guild)
        synced = await self.tree.sync(guild=self._guild)
        log.info("Discord : %d commandes synchronisées", len(synced))
        self.purge_task.start()

    async def on_ready(self) -> None:
        log.info("Discord : connecté en tant que %s", self.user)

    async def _text_channel(self, channel_id: int) -> discord.TextChannel:
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError(f"Le salon {channel_id} n'est pas un salon textuel")
        return channel

    async def post_to_staff(self, report: Report) -> None:
        """Publie un dossier dans #signalements avec les boutons de suivi."""
        channel = await self._text_channel(self.config.discord.reports_channel_id)
        msg = await channel.send(
            content=f"<@&{self.config.discord.staff_role_id}>",
            embed=build_report_embed(report),
            view=build_staff_view(report),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        self.store.set_staff_message(report.id, msg.id)

    async def open_help_thread(self, interaction: discord.Interaction) -> None:
        if not self.limiter.allow(f"discord:{interaction.user.id}"):
            await interaction.response.send_message(messages.RATE_LIMITED, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self._create_help_thread(interaction)
        except Exception:
            log.exception("Impossible de créer le fil d'aide")
            await interaction.followup.send(
                "Oups, le fil privé n'a pas pu être créé. Réessaie dans quelques minutes. "
                "En attendant :\n\n" + messages.CRISIS_RESOURCES,
                ephemeral=True,
            )

    async def _create_help_thread(self, interaction: discord.Interaction) -> None:
        channel = await self._text_channel(self.config.discord.help_channel_id)
        report = self.store.create(
            source=Source.DISCORD,
            kind=Kind.HELP,
            reporter=f"{interaction.user} ({interaction.user.id})",
            description="Demande à parler à un·e intervenant·e.",
        )
        thread = await channel.create_thread(
            name=f"aide-{report.id}",
            type=discord.ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=10080,  # 7 jours
        )
        await thread.add_user(interaction.user)
        await thread.send(
            messages.HELP_THREAD_WELCOME.format(user=interaction.user.mention)
            + f"\n\n{messages.CRISIS_RESOURCES}",
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        report = self.store.set_location(report.id, f"Fil privé {thread.mention}", thread.jump_url)
        await self.post_to_staff(report)
        await interaction.followup.send(
            messages.HELP_THREAD_CREATED.format(thread=thread.mention), ephemeral=True
        )

    @tasks.loop(time=dtime(hour=4, tzinfo=timezone.utc))
    async def purge_task(self) -> None:
        deleted = self.store.purge_closed(self.config.retention_days)
        if deleted:
            log.info("Purge : %d dossier(s) fermé(s) supprimé(s)", deleted)


def register_commands(bot: AideBot) -> None:
    tree = bot.tree

    @tree.command(name="aide", description="Obtenir de l'aide ou parler en privé à un·e intervenant·e")
    async def aide(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Besoin d'aide ?",
            description=f"{messages.HELP_INTRO}\n\n{messages.CRISIS_RESOURCES}\n\n{messages.NOT_AN_EMERGENCY}",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=build_help_view(), ephemeral=True)

    @tree.command(name="signaler", description="Signaler un comportement à l'équipe d'intervention")
    async def signaler(interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ReportModal())

    @tree.context_menu(name="Signaler ce message")
    async def signaler_message(interaction: discord.Interaction, message: discord.Message) -> None:
        excerpt = message.content[:300] if message.content else "(pas de texte)"
        where = getattr(message.channel, "name", None)
        await interaction.response.send_modal(
            ReportModal(
                target=f"{message.author} ({message.author.id})"[:100],
                location=f"#{where}" if where else None,
                evidence=f"{message.jump_url}\n« {excerpt} »"[:500],
            )
        )

    @tree.command(name="panneau", description="Publier le panneau d'aide dans ce salon (équipe)")
    @app_commands.default_permissions(manage_guild=True)
    async def panneau(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Besoin d'aide ou envie de signaler quelque chose ?",
            description=(
                "💬 **Parler à un·e intervenant·e** : ouvre un fil privé avec l'équipe.\n"
                "🚩 **Signaler** : envoie un signalement (anonyme possible).\n"
                "Tu peux aussi faire clic droit sur un message → *Applications* → "
                "*Signaler ce message*.\n\n" + messages.CRISIS_RESOURCES
            ),
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=build_panel_view())  # type: ignore[union-attr]
        await interaction.response.send_message("Panneau publié.", ephemeral=True)

    @tree.command(name="stats", description="Nombre de dossiers par type et statut (équipe)")
    @app_commands.default_permissions(manage_guild=True)
    async def stats(interaction: discord.Interaction) -> None:
        data = bot.store.stats()
        lines = [f"`{k}` : {v}" for k, v in sorted(data.items())] or ["Aucun dossier."]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
