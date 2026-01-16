from __future__ import annotations
import discord

from ..services import validators, render

RATE_LIMIT_MSG = "連続操作は制限されています。少し待ってから試してください。"
LINK_ERR = "リンクは禁止です。URLや招待コードを削除して再入力してください。"
MENTION_ERR = "メンションは使用できません。"
LEN_ERR = "文字数が長すぎます。短くしてください。"
NAME_REQ = "名前は必須です。入力してください。"

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

    # Row 0: state buttons (color coded)
    @discord.ui.button(label="好調", style=discord.ButtonStyle.success, custom_id="panel:state:good", row=0)
    async def st_good(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_state(interaction, "好調")

    @discord.ui.button(label="通常", style=discord.ButtonStyle.primary, custom_id="panel:state:norm", row=0)
    async def st_norm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_state(interaction, "通常")

    @discord.ui.button(label="省エネ", style=discord.ButtonStyle.secondary, custom_id="panel:state:low", row=0)
    async def st_low(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_state(interaction, "省エネ")

    @discord.ui.button(label="休憩", style=discord.ButtonStyle.danger, custom_id="panel:state:rest", row=0)
    async def st_rest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_state(interaction, "休憩")

    # Row 1: actions (color coded)
    @discord.ui.button(label="編集", style=discord.ButtonStyle.primary, custom_id="panel:edit", row=1)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        defaults = {"name": profile.name, "condition": profile.condition, "hobby": profile.hobby, "care": profile.care, "one": profile.one}
        await interaction.response.send_modal(ProfileEditModal(self.bot, defaults))

    @discord.ui.button(label="表示", style=discord.ButtonStyle.secondary, custom_id="panel:show", row=1)
    async def show(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        profile = await self.bot.db.get_profile(gid, interaction.user.id)
        emb = render.build_profile_embed(
            display_name=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
            state=profile.state,
            state_updated_at=profile.state_updated_at,
            name=profile.name,
            condition=profile.condition,
            hobby=profile.hobby,
            care=profile.care,
            one=profile.one,
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        await self.bot.audit(interaction, action="panel_show", result="ok", reason=None)

    @discord.ui.button(label="ヘルプ", style=discord.ButtonStyle.secondary, custom_id="panel:help", row=1)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.delete_if_old_panel(interaction)
        await interaction.response.send_message(render.help_text(), ephemeral=True)
        await self.bot.audit(interaction, action="help", result="ok", reason=None)

    async def _handle_state(self, interaction: discord.Interaction, state: str) -> None:
        gid = interaction.guild_id
        if gid is None:
            return
        await self.bot.delete_if_old_panel(interaction)

        if not self.bot.limiter.allow(gid, interaction.user.id, "state_change"):
            await interaction.response.send_message(RATE_LIMIT_MSG, ephemeral=True)
            await self.bot.audit(interaction, action="state_change", result="ng", reason="rate_limit")
            return

        _ = await self.bot.db.get_profile(gid, interaction.user.id)
        await self.bot.db.update_state(gid, interaction.user.id, state)
        await interaction.response.send_message(f"状態を「{state}」にしました。", ephemeral=True)
        await self.bot.audit(interaction, action="state_change", result="ok", reason=None)

        await self.bot.upsert_public_profile(interaction)
