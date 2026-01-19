from __future__ import annotations
from datetime import datetime
import discord
from ..models import STATE_CHOICES

STATE_COLORS: dict[str, int] = {
    "元気": 0x57F287,  # green
    "通常": 0x3498DB,  # blue
    "低速": 0xFEE75C,  # yellow
    "しんどい": 0xED4245,  # red
}

def fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y/%m/%d")

def safe(v: str) -> str:
    v = (v or "").strip()
    return v if v else "（未設定）"

def build_panel_embed() -> discord.Embed:
    emb = discord.Embed(title="🍪Profile", color=0x95A5A6)
    emb.description = "\n".join([
        "- 「編集」ボタンでプロフィールを作成",
        "- 体調や気分で「元気」「通常」「低速」「しんどい」を選択",
        "- 「表示」ボタンでプレビューを確認",
        "- 編集後のメッセージ（青色文章）を削除",
        "- 入力制約：リンク禁止・メンション禁止・文字数制限あり",
    ])
    return emb

def build_profile_embed(
    *,
    display_name: str,
    avatar_url: str | None,
    state: str,
    state_updated_at: datetime,
    name: str,
    condition: str,
    hobby: str,
    care: str,
    one: str,
) -> discord.Embed:
    if state not in STATE_CHOICES:
        state = "通常"
    emb = discord.Embed(
        title=f"{display_name}さんのプロフィール",
        color=STATE_COLORS.get(state, 0x3498DB),
    )
    if avatar_url:
        emb.set_thumbnail(url=avatar_url)

    emb.add_field(name="名前", value=safe(name), inline=False)
    emb.add_field(name="診断名/入場条件", value=safe(condition), inline=False)
    emb.add_field(name="趣味", value=safe(hobby), inline=False)
    emb.add_field(name="配慮して欲しい事", value=safe(care), inline=False)
    emb.add_field(name="自由に一言", value=safe(one), inline=False)

    emb.set_footer(text=f"状態：{state}（更新：{fmt_date(state_updated_at)}）")
    return emb
