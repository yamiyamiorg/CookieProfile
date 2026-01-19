from __future__ import annotations
import discord

EMBED_COLOR = 0xFFC0CB


def safe(v: str) -> str:
    v = (v or "").strip()
    return v if v else "（未設定）"


def build_panel_embed() -> discord.Embed:
    emb = discord.Embed(title="🍪Profile", color=EMBED_COLOR)
    emb.description = "\n".join([
        "- 「編集」ボタンでプロフィールを作成",
        "- 「表示」ボタンでプレビューを確認",
        "- 編集後のメッセージ（青色文章）を削除",
        "- 入力制約：リンク禁止・メンション禁止・文字数制限あり",
    ])
    return emb


def build_profile_embed(
    *,
    display_name: str,
    avatar_url: str | None,
    name: str,
    condition: str,
    hobby: str,
    care: str,
    one: str,
) -> discord.Embed:
    emb = discord.Embed(
        title=f"{display_name}さんのプロフィール",
        color=EMBED_COLOR,
    )
    if avatar_url:
        emb.set_thumbnail(url=avatar_url)

    emb.add_field(name="名前", value=safe(name), inline=False)
    emb.add_field(name="診断名/入場条件", value=safe(condition), inline=False)
    emb.add_field(name="趣味", value=safe(hobby), inline=False)
    emb.add_field(name="配慮して欲しい事", value=safe(care), inline=False)
    emb.add_field(name="自由に一言", value=safe(one), inline=False)

    return emb
