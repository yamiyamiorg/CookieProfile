# 🍪Profile Bot

最終仕様（要点）
- スラッシュコマンドは **/profilesetup** と **/p** のみ
- /profilesetup で「ボタンを置くチャンネル」を指定 → そのチャンネルに **ヘルプ＋ボタン付き入口Embed**を設置（スティッキー）
- 入口のボタン：状態4（色分け）＋編集＋表示＋ヘルプ
- プロフィールEmbed：絵文字なし、**フィールド名＝項目名**、右上にユーザーのアバター表示
- /p：従来仕様（確認UI、VC内チャット限定＋VC参加中必須、30分後自動削除）

## 起動（Docker）
```bash
cp .env.example .env
# .env に DISCORD_TOKEN を設定
docker compose up -d --build
docker compose logs -f
```

## セットアップ（管理者）
`/profilesetup channel:#プロフィールチャンネル log_channel:#ログ(任意)`

## 回帰テスト（ローカル）
```bash
python -m unittest discover -s tests -v
```
