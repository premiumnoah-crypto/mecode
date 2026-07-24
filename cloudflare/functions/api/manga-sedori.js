// Cloudflare Pages Function — 新連載マンガ せどり判定データAPI
// ---------------------------------------------------------------------------
// これを research-radar 側のリポジトリの functions/api/manga-sedori.js に置くと、
//   https://<あなたのサイト>/api/manga-sedori
// という「同一オリジン」のJSON APIになります。フロントエンドはここを fetch する
// だけでよく、CORS・bot403・APIキー露出の問題がすべて解消します。
//
// 仕組み: サーバー側(エッジ)で mecode が毎日公開する latest.json を取得して
// 返すだけ。サーバー間通信なのでCORSは無関係。エッジキャッシュも効かせています。
//
// mecode の Pages URL に合わせて DATA_SOURCE を変更してください。
// （GitHub Pages を有効化すると下記の形のURLになります）
const DATA_SOURCE =
  "https://premiumnoah-crypto.github.io/mecode/latest.json";

export async function onRequest(context) {
  const cache = caches.default;
  const cacheKey = new Request(new URL(context.request.url).toString(),
                               context.request);

  // 30分エッジキャッシュ（更新は日次なので十分）
  let cached = await cache.match(cacheKey);
  if (cached) return cached;

  try {
    const upstream = await fetch(DATA_SOURCE, {
      cf: { cacheTtl: 1800, cacheEverything: true },
      headers: { "User-Agent": "manga-sedori-edge/1.0" },
    });
    if (!upstream.ok) {
      return json({ error: `upstream ${upstream.status}`,
                    source: DATA_SOURCE }, 502);
    }
    const data = await upstream.json();
    const res = json(data, 200, { "Cache-Control": "public, max-age=1800" });
    context.waitUntil(cache.put(cacheKey, res.clone()));
    return res;
  } catch (e) {
    return json({ error: "fetch_failed", message: String(e),
                  source: DATA_SOURCE }, 502);
  }
}

function json(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      ...extra,
    },
  });
}
