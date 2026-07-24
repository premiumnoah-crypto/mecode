"""Google Trends から検索関心を収集 (pytrends, 無料・無キー).

pytrends 未インストール / Googleのブロック時は静かに無効化される。
"""
from __future__ import annotations

import logging
from typing import Optional

from ..models import Title

log = logging.getLogger(__name__)


def collect(title: Title, cfg: dict) -> Optional[float]:
    """直近期間の平均検索関心 (0-100) を返す。失敗時 None。"""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.info("pytrends 未インストールのため Trends収集をスキップ")
        return None

    try:
        py = TrendReq(hl="ja-JP", tz=540)
        py.build_payload(
            [title.title],
            timeframe=cfg.get("timeframe", "now 7-d"),
            geo=cfg.get("geo", ""),
        )
        df = py.interest_over_time()
        if df is None or df.empty or title.title not in df:
            return None
        return float(df[title.title].mean())
    except Exception as e:  # pytrends は多様な例外を投げる
        log.warning("Google Trends エラー (%s): %s", title.title, e)
        return None
