# 🍪Profile Bot

最終仕様（要点）
- スラッシュコマンドは **/profilesetup** のみ
- /profilesetup で「ボタンを置くチャンネル」を指定 → そのチャンネルに **ヘルプ＋ボタン付き入口Embed**を設置（スティッキー）
- 入口のボタン：状態4（色分け）＋編集＋表示＋ヘルプ
- プロフィールEmbed：絵文字なし、**フィールド名＝項目名**、右上にユーザーのアバター表示

## 起動（Docker）
```bash
cp .env.example .env
# .env に DISCORD_TOKEN を設定
docker compose up -d --build
docker compose logs -f
```

## セットアップ（管理者）
`/profilesetup channel:#プロフィールチャンネル log_channel:#ログ(任意)`

## コマンド同期（古い /p の削除）
- 通常は起動時にグローバル/ギルド同期が走ります。
- すぐ反映したい場合は `.env` に `SYNC_GUILD_ID` を設定して再起動してください（対象ギルドで同期）。
- それでも残る場合は Discord Developer Portal の「Commands」から `/p` を削除してください。

## 回帰テスト（ローカル）
```bash
python -m unittest discover -s tests -v
```
