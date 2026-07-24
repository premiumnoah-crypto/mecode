"""AniList (GraphQL) コレクター.

X/Reddit/Google Trends は自動実行環境(データセンターIP)から 403/429 で遮断される
ため、キー不要・API公開のAniList GraphQLを一次データ源として用いる。

役割は2つ:
  1) discover(): 直近に連載開始した日本のマンガをトレンド順に取得し、監視候補
     (実在タイトル+ジャンル)を返す。→ seed_titles.yaml を実データで満たす。
  2) collect(): 個別作品を検索し、popularity/favourites/averageScore を取得して
     既存の Signals(バズ/コレクター/トレンド) の入力に流し込む。

いずれもネットワーク/解析エラー時は静かに空を返し、パイプラインは継続する。
"""
from __future__ import annotations

import datetime
import logging
import math
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)

_ENDPOINT = "https://graphql.anilist.co"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "mecode-manga-resale-analyzer/1.0",
}
_TIMEOUT = 25

# AniList(英語ジャンル) → config.yaml の genre_tailwind キー(日本語) への対応。
# 優先度順に評価し、最初に一致したものを採用する。
_GENRE_PRIORITY = [
    ("Horror", "ホラー"),
    ("Sports", "スポーツ"),
    ("Mystery", "サスペンス"),
    ("Thriller", "サスペンス"),
    ("Psychological", "サスペンス"),
    ("Supernatural", "ダークファンタジー"),
    ("Fantasy", "異世界"),
    ("Action", "アクション"),
    ("Adventure", "バトル"),
    ("Slice of Life", "日常"),
    ("Romance", "ラブコメ"),
    ("Comedy", "ギャグ"),
    ("Drama", "サスペンス"),
]


def _query(query: str, variables: dict) -> Optional[dict]:
    try:
        r = requests.post(
            _ENDPOINT,
            json={"query": query, "variables": variables},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
        if "errors" in payload and payload["errors"]:
            log.warning("AniList GraphQLエラー: %s", payload["errors"])
        return payload.get("data")
    except (requests.RequestException, ValueError) as e:
        log.warning("AniListリクエスト失敗: %s", e)
        return None


def _map_genre(genres: list[str]) -> str:
    gset = set(genres or [])
    # Romance+Comedy はラブコメを優先
    if "Romance" in gset:
        return "ラブコメ"
    for name, jp in _GENRE_PRIORITY:
        if name in gset:
            return jp
    return "不明"


def _fuzzydate_to_str(d: dict) -> Optional[str]:
    if not d:
        return None
    y, m, day = d.get("year"), d.get("month"), d.get("day")
    if not y:
        return None
    return f"{y:04d}-{(m or 1):02d}-{(day or 1):02d}"


_DISCOVER_QUERY = """
query ($page:Int, $perPage:Int, $start:FuzzyDateInt) {
  Page(page:$page, perPage:$perPage) {
    media(
      type: MANGA
      countryOfOrigin: "JP"
      format_in: [MANGA, ONE_SHOT]
      startDate_greater: $start
      sort: [TRENDING_DESC, POPULARITY_DESC]
    ) {
      id
      title { native romaji english }
      genres
      popularity
      favourites
      averageScore
      trending
      startDate { year month day }
      status
      isAdult
      siteUrl
    }
  }
}
"""


def discover(cfg: dict) -> list[dict[str, Any]]:
    """直近に連載開始した日本マンガの監視候補レコードを返す。

    戻り値の各要素は seed_titles.yaml に追記できる dict:
      {title, title_en, genre, platform, new_author, color_opening,
       search_terms, volume1_date}
    """
    acfg = cfg.get("anilist", {})
    if not acfg.get("enabled", True):
        return []

    months = int(acfg.get("discover_months", 18))
    per_page = min(50, int(acfg.get("discover_limit", 30)))
    min_pop = int(acfg.get("min_popularity", 30))

    cutoff = datetime.date.today() - datetime.timedelta(days=months * 30)
    start_int = int(cutoff.strftime("%Y%m%d"))

    data = _query(_DISCOVER_QUERY,
                  {"page": 1, "perPage": per_page, "start": start_int})
    if not data:
        return []

    media = (data.get("Page") or {}).get("media") or []
    records: list[dict[str, Any]] = []
    for m in media:
        if m.get("isAdult"):
            continue
        if (m.get("popularity") or 0) < min_pop:
            continue
        t = m.get("title") or {}
        name = t.get("native") or t.get("romaji") or t.get("english")
        if not name:
            continue
        search = [s for s in (t.get("romaji"), t.get("english")) if s]
        records.append({
            "title": name,
            "title_en": t.get("english") or t.get("romaji"),
            "platform": "不明",           # AniListは掲載誌情報を持たない
            "genre": _map_genre(m.get("genres")),
            "new_author": False,
            "color_opening": False,
            "search_terms": search,
            "volume1_date": _fuzzydate_to_str(m.get("startDate")),
        })

    if records:
        log.info("AniList: 監視候補 %d件を取得", len(records))
    return records


def merge_into_seed(records: list[dict], seed_path: str) -> int:
    """discover()のレコードを seed_titles.yaml に重複なく追記。追加件数を返す。"""
    import yaml

    if not records:
        return 0
    with open(seed_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    titles = data.get("titles") or []
    existing = {t.get("title") for t in titles if isinstance(t, dict)}

    added = 0
    for rec in records:
        if rec["title"] in existing:
            continue
        titles.append(rec)
        existing.add(rec["title"])
        added += 1

    if added:
        data["titles"] = titles
        with open(seed_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        log.info("seed_titles.yaml に AniList候補 %d件 追記", added)
    return added


_SEARCH_QUERY = """
query ($search:String) {
  Media(type: MANGA, search: $search, sort: [SEARCH_MATCH]) {
    popularity
    favourites
    averageScore
    trending
    title { native romaji english }
  }
}
"""


def collect(title, cfg: dict) -> Optional[dict]:
    """作品名でAniListを検索し、シグナル入力用の指標を返す。

    戻り値: {"popularity", "favourites", "average", "trending_norm"} or None
      trending_norm は 0-100 に正規化済み(trends_valueに使える)。
    """
    acfg = cfg.get("anilist", {})
    if not acfg.get("enabled", True):
        return None

    # 日本語タイトル優先、無ければ英語名で検索
    query_name = getattr(title, "title", None)
    data = _query(_SEARCH_QUERY, {"search": query_name})
    media = (data or {}).get("Media")
    if not media and getattr(title, "title_en", None):
        data = _query(_SEARCH_QUERY, {"search": title.title_en})
        media = (data or {}).get("Media")
    if not media:
        return None

    trending = media.get("trending") or 0
    # trending(直近活動数)を対数で0-100へ
    trending_norm = 0.0
    if trending > 0:
        trending_norm = max(0.0, min(
            100.0, 100.0 * math.log1p(trending) / math.log1p(500)))

    return {
        "popularity": float(media.get("popularity") or 0),
        "favourites": float(media.get("favourites") or 0),
        "average": float(media.get("averageScore") or 0),
        "trending_norm": round(trending_norm, 1),
    }
