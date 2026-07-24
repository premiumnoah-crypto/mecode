"""Reddit から海外人気シグナルを収集.

認証なしの公開検索JSON (https://www.reddit.com/r/<sub>/search.json) を使う。
User-Agent さえ付ければ無料・無キーで動く。アクセス過多時は静かに失敗する。
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from ..models import Title

log = logging.getLogger(__name__)

_UA = "mecode-manga-resale-analyzer/1.0 (by /u/anonymous)"


def collect(title: Title, cfg: dict) -> Optional[dict]:
    """1作品ぶんのRedditシグナルを返す。失敗/該当なしは None。

    戻り値: {"score": float, "posts": int}
    """
    query = title.title_en or title.title
    subreddits = cfg.get("subreddits", ["manga"])
    time_filter = cfg.get("time_filter", "month")
    limit = int(cfg.get("limit", 25))

    total_score = 0.0
    total_posts = 0
    any_ok = False

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {
            "q": query,
            "restrict_sr": 1,
            "sort": "top",
            "t": time_filter,
            "limit": limit,
        }
        try:
            r = requests.get(
                url, params=params, headers={"User-Agent": _UA}, timeout=20
            )
            r.raise_for_status()
            data = r.json()
            any_ok = True
        except (requests.RequestException, ValueError) as e:
            log.warning("Reddit エラー (r/%s, %s): %s", sub, title.title, e)
            continue

        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            # コメントはエンゲージメントとして1.5倍重み
            total_score += d.get("score", 0) + 1.5 * d.get("num_comments", 0)
            total_posts += 1

        time.sleep(1)  # 礼儀としてのレート制御

    if not any_ok:
        return None
    return {"score": float(total_score), "posts": total_posts}
