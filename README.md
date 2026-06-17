# mecode — 新連載マンガ せどり判定システム

新連載マンガを **X(Twitter)・Reddit・Google Trends** で多角的にリサーチし、
過去のヒット/プレミア化事例（呪術廻戦・SPY×FAMILY・ダンダダン等）に照らして

- **バズりそうか (virality)**
- **アニメ化/映画化しそうか (adaptation)**
- **コミックス1巻の初版・未開封を積み増し → 1年後に定価10倍で売れそうか (resale)**

を 0-100 でスコアリングし、**毎日朝9時(JST)に自動でレポートを生成してメール通知**します。
実行基盤は **GitHub Actions cron** なので、PCを起動していなくても毎朝動きます。

> ⚠️ **重要**：スコアは過去のヒット要因に基づく*確率的な期待値*であり、アニメ化・転売益を
> 保証するものではありません。せどり・投資は自己責任で行ってください。
> また X API は有料/制限あり、Reddit公開エンドポイントもブロックされる場合があるため、
> 取得できなかったデータ源はレポート上で明示し、その分スコアの信頼度を下げています。

---

## 仕組み

```
data/seed_titles.yaml   ← 監視する新連載リスト(メタデータ付き)
        │
        ▼
  collectors/            ← X / Reddit / Google Trends からシグナル収集（鍵が無い源は自動スキップ）
        │
        ▼
  scoring.py             ← 重み付きルーブリックで virality / adaptation / resale を算出
        │                   (historical_hits.yaml の経験則を反映)
        ▼
  report.py              ← Markdown + HTML レポート生成 / reports/ に保存
        │
        ▼
  notify.py (メール)  +  GitHub Actions が reports/ をリポジトリにコミット
```

判定ロジック・しきい値・重み付けはすべて `config.yaml` で調整できます。

---

## セットアップ

### 1. GitHub Secrets を登録
リポジトリの **Settings → Secrets and variables → Actions** で以下を登録します
（未登録の源は自動的にスキップされ、パイプライン自体は動きます）。

| Secret | 必須 | 用途 |
|--------|:---:|------|
| `X_BEARER_TOKEN` | 推奨 | X API v2 のエンゲージメント取得（[X Developer](https://developer.x.com/)） |
| `SMTP_HOST` | メール通知に必須 | 例: `smtp.gmail.com` |
| `SMTP_PORT` | 〃 | 例: `587` |
| `SMTP_USER` | 〃 | 送信元アドレス |
| `SMTP_PASS` | 〃 | Gmailなら2段階認証+**アプリパスワード** |
| `REPORT_TO` | 任意 | 送信先。未設定なら `SMTP_USER` 宛 |
| `ANTHROPIC_API_KEY` | 任意 | Claudeによる定性サマリーを足したい場合 |

> Reddit / Google Trends は**キー不要**（無料の公開エンドポイント）。

### 2. 監視対象を登録
`data/seed_titles.yaml` に新連載を追記します。メタデータが多いほど精度が上がります。

```yaml
titles:
  - title: "作品名"
    title_en: "English Title"   # Reddit検索用
    platform: "週刊少年ジャンプ"  # config.yaml の platform_tiers のキー
    genre: "ダークファンタジー"    # config.yaml の genre_tailwind のキー
    volume1_date: "2026-08-04"   # 1巻発売日（せどり判定の起点）
    new_author: true             # 新人初連載＝初版が希少化しやすい
    color_opening: true          # 巻頭/開幕カラー＝編集部プッシュ
```

### 3. スケジュール
`.github/workflows/daily-manga-report.yml` の cron は `0 0 * * *`（= **09:00 JST**）。
`workflow_dispatch` で手動実行もできます。

---

## ローカル実行

```bash
pip install -r requirements.txt
cp .env.example .env        # 値を埋める
export $(grep -v '^#' .env | xargs)
python -m src.main --no-email   # メール送信せず標準出力に出すだけ
```

テスト:

```bash
python tests/test_scoring.py    # もしくは: python -m pytest tests/ -q
```

---

## スコアリングの考え方（せどり観点）

`resale`（初版10倍の妙味）は次の3要素の重み付き合成です（`config.yaml` で調整可）:

1. **adaptation（ヒット確率）** … アニメ化発表の瞬間に中古相場が跳ねるため、需要爆発の確率。
2. **scarcity（初版希少性）** … 新人初連載ほど初版部数が絞られ希少化しやすい。逆にWeb発の大型作品は
   初版が潤沢で高倍率になりにくい（例：ダンダダン1巻は希少化したが、増刷が早い作品は伸びにくい）。
3. **collector（コレクター需要）** … 海外(英語圏)人気が高いほど世界的な買い手がつき高倍率化しやすい。

`resale >= 70` かつ `adaptation >= 50` で **BUY（積み増し推奨）** と判定し、
スコア帯に応じて推奨積み増し冊数を提示します。

---

## カスタマイズ早見表

| やりたいこと | いじる場所 |
|---|---|
| 監視作品を増やす | `data/seed_titles.yaml` |
| BUY判定を厳しく/緩く | `config.yaml` → `thresholds` |
| 各シグナルの重み変更 | `config.yaml` → `weights` |
| 媒体/ジャンルの評価変更 | `config.yaml` → `platform_tiers` / `genre_tailwind` |
| 通知時刻の変更 | `.github/workflows/daily-manga-report.yml` の `cron` |
| 参照する過去事例の追加 | `data/historical_hits.yaml` |
