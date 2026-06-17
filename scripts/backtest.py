"""ルーブリック検証(バックテスト).

data/historical_hits.yaml の過去事例に、当時観測できたであろうシグナルを
近似的に与えてスコアリングし、実際の結果(アニメ化/プレミア倍率)と
判定が整合するかを確認する。重み付け調整の指針に使う。

実行: python -m scripts.backtest
"""
from __future__ import annotations

import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Title, Signals  # noqa: E402
from src import scoring  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name: str) -> dict:
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _synth_signals(case: dict) -> Signals:
    """early_signals の強さから当時のシグナルを近似生成する。"""
    sigs = case.get("early_signals", [])
    text = " ".join(sigs)
    # キーワードの強さで概算（実データの代理）
    x = 60000 if "バズ" in text else (25000 if "話題" in text else 8000)
    reddit = 4000 if ("海外" in text or "Reddit" in text or "世界" in text) else 800
    trends = 85 if ("バズ" in text or "記録" in text) else 55
    return Signals(x_engagement=x, reddit_score=reddit, trends_value=trends,
                   sources_used=["X", "Reddit", "Trends"])


def main() -> int:
    cfg = _load("config.yaml")
    hits = _load("data/historical_hits.yaml")["cases"]

    print(f"{'作品':<14}{'viral':>6}{'adapt':>6}{'resale':>7}"
          f"{'判定':>7}  実績(anime/倍率)")
    print("-" * 60)

    anime_ok = 0
    anime_total = 0
    for c in hits:
        t = Title(
            title=c["title"], platform=c.get("platform", "不明"),
            genre=c.get("genre", "不明"), new_author=c.get("new_author", False),
        )
        s = scoring.score_title(t, _synth_signals(c), cfg)
        out = c.get("outcome", {})
        anime = out.get("anime", False)
        x_mult = out.get("vol1_premium_x", "?")
        print(f"{c['title']:<14}{s.virality:>6.0f}{s.adaptation:>6.0f}"
              f"{s.resale:>7.0f}{s.recommendation:>7}  "
              f"{'○' if anime else '×'}/{x_mult}倍")
        if anime:
            anime_total += 1
            # アニメ化された作品は adaptation がwatch閾値以上であってほしい
            if s.adaptation >= cfg["thresholds"]["watch"]:
                anime_ok += 1

    print("-" * 60)
    rate = (anime_ok / anime_total * 100) if anime_total else 0
    print(f"アニメ化作品の適合率(adaptation>=watch): {anime_ok}/{anime_total} "
          f"({rate:.0f}%)")
    print("\n※ これは過去事例での妥当性確認。重みは config.yaml の weights で調整可。")
    # 過半数が整合していれば成功扱い
    return 0 if rate >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
