from __future__ import annotations
from datetime import timedelta
import discord

from ..services import validators, render
from ..storage.db import utcnow

RATE_LIMIT_MSG = "連続操作は制限されています。少し待ってから試してください。"
LINK_ERR = "リンクは禁止です。URLや招待コードを削除して再入力してください。"
MENTION_ERR = "メンションは使用できません。"
LEN_ERR = "文字数が長すぎます。短くしてください。"
NAME_REQ = "名前は必須です。入力してください。"

NOT_VC_CHAT = "公開投稿はVC内チャットでのみ可能です。VCのチャットから /p を実行してください。"
NOT_IN_VC = "VC参加中のみ投稿できます。先にそのVCへ参加してください。"

def _is_vc_chat_channel(ch: discord.abc.GuildChannel) -> bool:
    return isinstance(ch, (discord.VoiceChannel, discord.StageChannel))

class ProfileEditModal(discord.ui.Modal):
    def __init__(self, bot: "CookieProfileBot", defaults: dict[str, str]):
        super().__init__(title="🍪Profile 編集", timeout=None)
        self.bot = bot

        self.name = discord.ui.TextInput(
            label="名前（必須）",
            required=True,
            max_length=validators.LIMITS.name,
            default=defaults.get("name", ""),
        )
        self.condition = discord.ui.TextInput(
            label="診断名/入場条件（任意）",
            required=False,
            max_length=validators.LIMITS.condition,
            default=defaults.get("condition", ""),
        )
        self.hobby = discord.ui.TextInput(
            label="趣味（任意）",
            required=False,
            max_length=validators.LIMITS.hobby,
            default=defaults.get("hobby", ""),
        )
        self.care = discord.ui.TextInput(
            label="配慮して欲しい事（任意）",
            required=False,
            max_length=validators.LIMITS.care,
            default=defaults.get("care", ""),
        )
        self.one = discord.ui.TextInput(
            label="自由に一言（任意）",
            required=False,
            max_length=validators.LIMITS.one,
            default=defaults.get("one", ""),
        )

        # No placeholders per spec
        for it in (self.name, self.condition, self.hobby, self.care, self.one):
            it.placeholder = None

        self.add_item(self.name)
        self.add_item(self.condition)
        self.add_item(self.hobby)
        self.add_item(self.care)
        self.add_item(self.one)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        gid = interaction.guild_id
        if gid is None:
            return
        if not self.bot.limiter.allow(gid, interaction.user.id, "modal_save"):
            await interaction.response.send_message(RATE_LIMIT_MSG, ephemeral=True)
            return

        name = (self.name.value or "").strip()
        condition = (self.condition.value or "").strip()
        hobby = (self.hobby.value or "").strip()
        care = (self.care.value or "").strip()
        one = (self.one.value or "").strip()

        if not name:
            await interaction.response.send_message(NAME_REQ, ephemeral=True)
            return

        for v in (name, condition, hobby, care, one):
            if validators.contains_link(v):
                await interaction.response.send_message(LINK_ERR, ephemeral=True)
                await self.bot.audit(interaction, action="edit_modal", result="ng", reason="invalid_input")
                return
            if validators.contains_mention(v):
                await interaction.response.send_message(MENTION_ERR, ephemeral=True)
                await self.bot.audit(interaction, action="edit_modal", result="ng", reason="invalid_input")
                return

        bad_field = validators.first_violating_field_length(name, condition, hobby, care, one)
        if bad_field:
            await interaction.response.send_message(LEN_ERR, ephemeral=True)
            await self.bot.audit(interaction, action="edit_modal", result="ng", reason="invalid_input")
            return

        # Ensure profile exists
        _ = await self.bot.db.get_profile(gid, interaction.user.id)
        await self.bot.db.update_profile_fields(gid, interaction.user.id, name=name, condition=condition, hobby=hobby, care=care, one=one)

        await interaction.response.send_message("保存しました。", ephemeral=True)
        await self.bot.audit(interaction, action="edit_modal", result="ok", reason=None)

        # Update (or recover) public profile message in configured channel
        await self.bot.upsert_public_profile(interaction)

class ProfilePanelView(discord.ui.View):
    """
    Persistent view for the sticky entry message.
    """
    def __init__(self, bot: "CookieProfileBot"):
        super().__init__(timeout=None)
        self.bot = bot

    # Row 0: actions
    @discord.ui.button(label="編集", style=discord.ButtonStyle.primary, custom_id="panel:edit", row=0)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        defaults = {"name": profile.name, "condition": profile.condition, "hobby": profile.hobby, "care": profile.care, "one": profile.one}
        await interaction.response.send_modal(ProfileEditModal(self.bot, defaults))

    @discord.ui.button(label="表示", style=discord.ButtonStyle.secondary, custom_id="panel:show", row=0)
    async def show(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        emb = render.build_profile_embed(
            display_name=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
            name=profile.name,
            condition=profile.condition,
            hobby=profile.hobby,
            care=profile.care,
            one=profile.one,
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        await self.bot.audit(interaction, action="panel_show", result="ok", reason=None)

    @discord.ui.button(label="自動表示：ON", style=discord.ButtonStyle.secondary, custom_id="panel:autopost", row=0)
    async def toggle_autopost(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        if not self.bot.limiter.allow(gid, interaction.user.id, "vc_autopost_toggle"):
            await interaction.response.send_message(RATE_LIMIT_MSG, ephemeral=True)
            await self.bot.audit(interaction, action="vc_autopost_toggle", result="ng", reason="rate_limit")
            return

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        enabled = not bool(profile.vc_autopost_enabled)
        await self.bot.db.set_vc_autopost_enabled(gid, interaction.user.id, enabled)
        button.label = "自動表示：ON" if enabled else "自動表示：OFF"
        try:
            if interaction.message:
                await interaction.message.edit(view=self)
        except Exception:
            pass

        await interaction.response.send_message(f"自動表示を{'ON' if enabled else 'OFF'}にしました。", ephemeral=True)
        await self.bot.audit(interaction, action="vc_autopost_toggle", result="ok", reason=None)

class PConfirmView(discord.ui.View):
    """
    Ephemeral confirm view for /p.
    """
    def __init__(self, bot: "CookieProfileBot"):
        super().__init__(timeout=180)
        self.bot = bot

    # Row 0: actions
    @discord.ui.button(label="プレビュー", style=discord.ButtonStyle.secondary, row=0)
    async def preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        emb = render.build_profile_embed(
            display_name=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
            name=profile.name,
            condition=profile.condition,
            hobby=profile.hobby,
            care=profile.care,
            one=profile.one,
        )
        await interaction.response.edit_message(content="プレビューです。", embed=emb, view=self)
        await self.bot.audit(interaction, action="p_preview", result="ok", reason=None)

    @discord.ui.button(label="投稿する", style=discord.ButtonStyle.primary, row=0)
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return

        if not self.bot.limiter.allow(gid, interaction.user.id, "p_post"):
            await interaction.response.send_message(RATE_LIMIT_MSG, ephemeral=True)
            await self.bot.audit(interaction, action="p_post", result="ng", reason="rate_limit")
            return

        ch = interaction.channel
        if ch is None or not _is_vc_chat_channel(ch):
            await interaction.response.send_message(NOT_VC_CHAT, ephemeral=True)
            await self.bot.audit(interaction, action="p_post", result="ng", reason="not_vc_chat")
            return

        # Must be in that VC
        if not getattr(interaction.user, "voice", None) or not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
            await self.bot.audit(interaction, action="p_post", result="ng", reason="not_in_vc")
            return
        if interaction.user.voice.channel.id != ch.id:
            await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
            await self.bot.audit(interaction, action="p_post", result="ng", reason="not_in_vc")
            return

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        emb = render.build_profile_embed(
            display_name=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
            name=profile.name,
            condition=profile.condition,
            hobby=profile.hobby,
            care=profile.care,
            one=profile.one,
        )
        try:
            msg = await ch.send(content=f"🍪Profile <@{interaction.user.id}>", embed=emb, allowed_mentions=discord.AllowedMentions(users=[interaction.user]))
        except Exception:
            await interaction.response.send_message("このVC内チャットに投稿できません（権限不足）。", ephemeral=True)
            await self.bot.audit(interaction, action="p_post", result="ng", reason="permission")
            return

        delete_at = utcnow() + timedelta(minutes=30)
        await self.bot.db.schedule_delete(gid, ch.id, msg.id, delete_at)

        await interaction.response.edit_message(content="投稿しました。（30分後に自動削除）", embed=None, view=None)
        await self.bot.audit(interaction, action="p_post", result="ok", reason=None)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="キャンセルしました。", embed=None, view=None)
        await self.bot.audit(interaction, action="p_cancel", result="ok", reason=None)
