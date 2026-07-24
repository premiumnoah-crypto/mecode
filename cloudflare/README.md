# research-radar (Cloudflare Pages) 側の修正ガイド

`manga-sedori` ページが「最新データを自動取得できない」原因と、その直し方です。

## 何が起きているか（根本原因）

`manga-sedori` ページの JavaScript が、ブラウザから直接
X / Reddit / RSS などの外部データを `fetch()` していると、以下で必ず失敗します。

1. **CORS** … これらのエンドポイントは `Access-Control-Allow-Origin` を返さないため、
   ブラウザがレスポンスを破棄する。
2. **bot 403** … Reddit・ナタリー等はブラウザ以外/自動アクセスを 403 で弾く。
3. **APIキー露出** … X API のトークンはクライアントJSに置けない（置くと漏れる）。

→ **データ取得はサーバー側（エッジ）に寄せ、ページは同一オリジンのJSONを読むだけ**にします。

## 直し方（どちらか）

### 方法A（推奨・堅牢）: Pages Function を追加
1. このフォルダの `functions/api/manga-sedori.js` を、research-radar リポジトリの
   同じパス `functions/api/manga-sedori.js` にコピーする。
2. ファイル冒頭の `DATA_SOURCE` を mecode の Pages URL に合わせる
   （例: `https://premiumnoah-crypto.github.io/mecode/latest.json`）。
3. フロントの取得先を **同一オリジン** に変更:
   ```js
   const res = await fetch("/api/manga-sedori", { cache: "no-store" });
   const data = await res.json();
   ```
4. デプロイ。以降 `/api/manga-sedori` が毎日更新の判定データを返します
   （サーバー間取得なのでCORS/403は発生せず、エッジで30分キャッシュ）。

### 方法B（最速・関数不要）: mecode の Pages を直接読む
GitHub Pages は `access-control-allow-origin: *` を返すので、ブラウザから直接読めます。
フロントの取得先をこう変えるだけ:
```js
const res = await fetch(
  "https://premiumnoah-crypto.github.io/mecode/latest.json",
  { cache: "no-store" }
);
const data = await res.json();
```

## データ形式（latest.json）

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-07-16 09:00",
  "title": "…",
  "summary": "…|null",
  "count": 12,
  "buy_count": 2,
  "disclaimer": "…",
  "items": [
    {
      "title": "作品名",
      "platform": "ジャンプ+",
      "genre": "ダークファンタジー",
      "volume1_date": "2026-08-04",
      "scores": { "virality": 62.1, "adaptation": 74.3, "resale": 71.0 },
      "recommendation": "BUY",     // BUY / WATCH / SKIP
      "buy_quantity": 5,
      "confidence": "medium",
      "rationale": ["…"],
      "sources_used": ["X", "Reddit"],
      "sources_failed": ["Trends"]
    }
  ]
}
```

`docs/index.html`（mecodeリポジトリ）に、このJSONを描画する最小フロントの実装例があります。
そのまま参考にできます。
