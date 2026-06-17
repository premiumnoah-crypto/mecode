"""X(Twitter) API v2 recent search でエンゲージメントを収集.

環境変数 X_BEARER_TOKEN が必要。未設定なら静かに無効化される（pipelineは継続）。
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import requests

from ..models import Title

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.twitter.com/2/tweets/search/recent"


def _build_query(title: Title, cfg: dict) -> str:
    terms = [title.title] + list(title.search_terms or [])
    # OR で結合（フレーズ検索）
    ors = " OR ".join(f'"{t}"' for t in terms if t)
    q = f"({ors})"
    if cfg.get("lang"):
        q += f" lang:{cfg['lang']}"
    if cfg.get("exclude_retweets", True):
        q += " -is:retweet"
    return q


def collect(title: Title, cfg: dict) -> Optional[dict]:
    """1作品ぶんのXシグナルを返す。失敗時は None。

    戻り値: {"engagement": float, "tweet_count": int}
    """
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        log.info("X_BEARER_TOKEN 未設定のため X収集をスキップ")
        return None

    params = {
        "query": _build_query(title, cfg),
        "max_results": min(int(cfg.get("max_results", 50)), 100),
        "tweet.fields": "public_metrics",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(_ENDPOINT, params=params, headers=headers, timeout=20)
        if r.status_code == 429:
            log.warning("X API レート制限。'%s' をスキップ", title.title)
            return None
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        log.warning("X API エラー (%s): %s", title.title, e)
        return None

    tweets = data.get("data", [])
    engagement = 0.0
    for t in tweets:
        m = t.get("public_metrics", {})
        engagement += (
            m.get("like_count", 0)
            + m.get("retweet_count", 0)
            + m.get("reply_count", 0)
            + m.get("quote_count", 0)
        )
    return {"engagement": float(engagement), "tweet_count": len(tweets)}
