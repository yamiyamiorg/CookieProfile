from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from datetime import timedelta

from ..config import AppConfig
from ..storage.db import Database, utcnow
from ..services.rate_limit import RateLimiter
from ..services.audit import make_log_line
from ..services.scheduler import DeleteScheduler
from ..services import render
from .views import ProfilePanelView, PConfirmView

class CookieProfileBot(commands.Bot):
    def __init__(self, cfg: AppConfig):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True  # for VC membership check
        intents.messages = True  # needed for bump (on_message)
        intents.message_content = False

        super().__init__(command_prefix="!", intents=intents)
        self.cfg = cfg
        self.db = Database(cfg.database_path)
        self.limiter = RateLimiter()
        self.scheduler = DeleteScheduler(self, self.db)

        # IMPORTANT: do not create discord.ui.View in __init__
        self.panel_view: ProfilePanelView | None = None
        self._synced_once: bool = False

    async def setup_hook(self) -> None:
        await self.db.connect()

        # Register persistent view after loop is running
        self.panel_view = ProfilePanelView(self)
        self.add_view(self.panel_view)

        self.scheduler.start()


    async def on_ready(self) -> None:
        # Force sync once to eliminate CommandSignatureMismatch caused by stale Discord command definitions.
        if self._synced_once:
            return
        self._synced_once = True

        try:
            if self.cfg.sync_guild_id:
                g = discord.Object(id=self.cfg.sync_guild_id)
                self.tree.copy_global_to(guild=g)
                await self.tree.sync(guild=g)
            else:
                # Sync per guild for fast propagation (safe if bot is in few guilds).
                for g0 in list(self.guilds):
                    g = discord.Object(id=g0.id)
                    self.tree.copy_global_to(guild=g)
                    await self.tree.sync(guild=g)

            # Also sync global (may take longer to propagate)
            await self.tree.sync()
        except Exception as e:
            print(f"[ProfileBot] command sync failed: {e!r}")

    async def close(self) -> None:
        try:
            await self.scheduler.stop()
        finally:
            await self.db.close()
            await super().close()

    async def audit(self, interaction: discord.Interaction, *, action: str, result: str, reason: str | None) -> None:
        gid = interaction.guild_id
        if gid is None:
            return
        cfg = await self.db.get_guild_config(gid)
        if not cfg.log_channel_id:
            return
        line = make_log_line(
            ts=utcnow(),
            guild_id=gid,
            user_id=interaction.user.id,
            action=action,
            channel_id=getattr(interaction.channel, "id", None),
            result=result,
            reason=reason,
        )
        ch = self.get_channel(cfg.log_channel_id)
        if ch:
            try:
                await ch.send(line)
            except Exception:
                pass

    async def delete_if_old_panel(self, interaction: discord.Interaction) -> None:
        gid = interaction.guild_id
        if gid is None or not interaction.message:
            return
        cfg = await self.db.get_guild_config(gid)
        latest = cfg.panel_message_id
        if latest and interaction.message.id != latest:
            try:
                await interaction.message.delete()
            except Exception:
                pass
            try:
                await interaction.followup.send("入口メッセージが更新されています。最新の入口を使ってください。", ephemeral=True)
            except Exception:
                pass

    async def ensure_sticky_panel(self, guild_id: int) -> None:
        cfg = await self.db.get_guild_config(guild_id)
        if not cfg.channel_id:
            return
        ch = self.get_channel(cfg.channel_id)
        if ch is None:
            try:
                ch = await self.fetch_channel(cfg.channel_id)
            except Exception:
                return

        emb = render.build_panel_embed()

        # if old exists, try edit, else create
        if cfg.panel_message_id:
            try:
                msg = await ch.fetch_message(cfg.panel_message_id)
                await msg.edit(embed=emb, view=self.panel_view)
                return
            except discord.NotFound:
                pass
            except Exception:
                pass

        # create new
        try:
            msg = await ch.send(embed=emb, view=self.panel_view)
            await self.db.set_panel_message_id(guild_id, msg.id)
        except Exception:
            return


    async def bump_panel(self, guild_id: int) -> None:
        """
        Bump (move) the sticky panel to the bottom by re-sending it.
        This creates a new message ID, so we update panel_message_id accordingly.
        Rate-limited via RateLimiter (panel_bump).
        """
        cfg = await self.db.get_guild_config(guild_id)
        if not cfg.channel_id:
            return

        # guild-level rate limit (use user_id=0 as system key)
        if not self.limiter.allow(guild_id, 0, "panel_bump"):
            return

        ch = self.get_channel(cfg.channel_id)
        if ch is None:
            try:
                ch = await self.fetch_channel(cfg.channel_id)
            except Exception:
                return

        # Send new panel first (so we never end up with none), then delete old (best-effort).
        emb = render.build_panel_embed()
        try:
            new_msg = await ch.send(embed=emb, view=self.panel_view)
        except Exception:
            return

        # Try delete old panel message to avoid duplicates (requires Manage Messages).
        if cfg.panel_message_id:
            try:
                old_msg = await ch.fetch_message(cfg.panel_message_id)
                await old_msg.delete()
            except Exception:
                pass

        await self.db.set_panel_message_id(guild_id, new_msg.id)

    async def on_message(self, message: discord.Message) -> None:
        # bump only when a human posts in the configured channel
        if message.guild is None:
            return
        if message.author.bot:
            return

        cfg = await self.db.get_guild_config(message.guild.id)
        if not cfg.channel_id:
            return
        if message.channel.id != cfg.channel_id:
            return

        # Do not bump if the panel is already the newest message (common when just deployed)
        if cfg.panel_message_id and message.id == cfg.panel_message_id:
            return

        await self.bump_panel(message.guild.id)

    async def upsert_public_profile(self, interaction: discord.Interaction) -> None:
        gid = interaction.guild_id
        if gid is None:
            return
        cfg = await self.db.get_guild_config(gid)
        if not cfg.channel_id:
            return

        ch = self.get_channel(cfg.channel_id)
        if ch is None:
            try:
                ch = await self.fetch_channel(cfg.channel_id)
            except Exception:
                return

        prof = await self.db.get_profile(gid, interaction.user.id)
        emb = render.build_profile_embed(
            display_name=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
            state=prof.state,
            state_updated_at=prof.state_updated_at,
            name=prof.name,
            condition=prof.condition,
            hobby=prof.hobby,
            care=prof.care,
            one=prof.one,
        )

        # Create if missing
        if not prof.public_message_id:
            try:
                msg = await ch.send(content=f"🍪Profile <@{interaction.user.id}>", embed=emb, allowed_mentions=discord.AllowedMentions(users=[interaction.user]))
                await self.db.set_public_message_id(gid, interaction.user.id, msg.id)
                await self.bump_panel(gid)
                await self.bump_panel(gid)
                return
            except Exception:
                return

        # Edit; recover if deleted
        try:
            msg = await ch.fetch_message(prof.public_message_id)
            await msg.edit(content=f"🍪Profile <@{interaction.user.id}>", embed=emb, allowed_mentions=discord.AllowedMentions(users=[interaction.user]))
            await self.bump_panel(gid)
        except discord.NotFound:
            try:
                msg = await ch.send(content=f"🍪Profile <@{interaction.user.id}>", embed=emb, allowed_mentions=discord.AllowedMentions(users=[interaction.user]))
                await self.db.set_public_message_id(gid, interaction.user.id, msg.id)
                await self.bump_panel(gid)
            except Exception:
                return
        except Exception:
            return

# Slash commands
class SetupCommands(app_commands.Group):
    def __init__(self, bot: CookieProfileBot):
        super().__init__(name="profilesetup", description="🍪Profile セットアップ")
        self.bot = bot

    @app_commands.command(name="run", description="入口（スティッキー）を設置する")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def run(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        log_channel: discord.TextChannel | None = None,
    ):
        gid = interaction.guild_id
        if gid is None:
            return

        # Read existing config BEFORE overwriting, so we can clean up old panel in a different channel (best effort).
        old_cfg = await self.bot.db.get_guild_config(gid)

        # Persist new target channel (and optional log channel)
        await self.bot.db.set_guild_config(
            gid,
            channel_id=channel.id,
            log_channel_id=log_channel.id if log_channel else None,
        )

        # If the panel existed in a previous channel and the channel changed, delete the old one (requires permissions).
        if old_cfg.panel_message_id and old_cfg.channel_id and old_cfg.channel_id != channel.id:
            try:
                old_ch = self.bot.get_channel(old_cfg.channel_id) or await self.bot.fetch_channel(old_cfg.channel_id)
                old_msg = await old_ch.fetch_message(old_cfg.panel_message_id)
                await old_msg.delete()
            except Exception:
                pass

        # Ensure (edit-or-create) sticky panel in the configured channel
        await self.bot.ensure_sticky_panel(gid)
        # Make sure the panel is the latest message (bump)
        await self.bot.bump_panel(gid)

        await interaction.response.send_message("入口メッセージを設置/更新しました。", ephemeral=True)


class PCommand:
    def __init__(self, bot: CookieProfileBot):
        self.bot = bot

    @app_commands.command(name="p", description="VC内チャットに一時的に🍪Profileを表示（確認あり）")
    async def p(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        if gid is None:
            return
        if not self.bot.limiter.allow(gid, interaction.user.id, "p_confirm"):
            await interaction.response.send_message("連続操作は制限されています。少し待ってから試してください。", ephemeral=True)
            await self.bot.audit(interaction, action="p_confirm", result="ng", reason="rate_limit")
            return

        _ = await self.bot.db.get_profile(gid, interaction.user.id)
        view = PConfirmView(self.bot)
        await interaction.response.send_message(
            "このVC内チャットにあなたの🍪Profileを投稿しますか？\n投稿すると全員に表示されます。\n投稿は30分後に自動削除されます。",
            ephemeral=True,
            view=view,
        )
        await self.bot.audit(interaction, action="p_confirm", result="ok", reason=None)

def create_bot() -> CookieProfileBot:
    load_dotenv()
    cfg = AppConfig.from_env()
    bot = CookieProfileBot(cfg)

    # /profilesetup run
    setup_group = SetupCommands(bot)
    bot.tree.add_command(setup_group)

    # /p
    p = PCommand(bot)
    bot.tree.add_command(p.p)

    return bot
