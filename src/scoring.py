"""多角的スコアリング・エンジン.

3つの合成スコアを 0-100 で算出する:
  - virality   : バズりそうか
  - adaptation : アニメ化/映画化しそうか
  - resale     : 初版を積み増して1年後に定価10倍で売れそうか（せどり妙味）

過去のヒット事例(historical_hits.yaml)の経験則をルーブリックに反映している。
スコアは「確率的な期待値」であって的中保証ではない点に注意。
"""
from __future__ import annotations

import math
from typing import Optional

from .models import Title, Signals, Scored


# --- 正規化ヘルパ -----------------------------------------------------
def _log_scale(value: Optional[float], full_at: float) -> float:
    """カウント系シグナルを 0-100 に対数圧縮する。

    full_at 付近で 100 に近づく。少数の超バズ作品に引っ張られすぎないように。
    """
    if not value or value <= 0:
        return 0.0
    score = 100.0 * math.log1p(value) / math.log1p(full_at)
    return max(0.0, min(100.0, score))


def _norm_weights(w: dict[str, float]) -> dict[str, float]:
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def _weighted(parts: dict[str, float], weights: dict[str, float]) -> float:
    w = _norm_weights(weights)
    return sum(parts.get(k, 0.0) * w.get(k, 0.0) for k in w)


# --- 個別スコア -------------------------------------------------------
def _editorial_score(title: Title, cfg: dict) -> float:
    base = cfg["platform_tiers"].get(title.platform, cfg["platform_tiers"]["不明"])
    if title.color_opening:
        base = min(100.0, base + 8)   # 巻頭/開幕カラーは編集部の本気度シグナル
    return float(base)


def _genre_score(title: Title, cfg: dict) -> float:
    return float(cfg["genre_tailwind"].get(title.genre, cfg["genre_tailwind"]["不明"]))


def _scarcity_score(title: Title) -> float:
    """初版の希少性。少部数で出るほど10倍化しやすい（=高得点）。"""
    score = 45.0
    if title.new_author:
        score += 35   # 新人初連載は初版が絞られがち→希少化しやすい
    # Web発の大型タイトルは初版が潤沢になりやすく希少性は下がる傾向
    if title.platform in ("ジャンプ+", "マガポケ", "コミックDAYS"):
        score -= 8
    return max(0.0, min(100.0, score))


def _collector_score(signals: Signals) -> float:
    """コレクター需要シグナル（海外人気が高いほど世界的買い手がつく）。"""
    reddit = _log_scale(signals.reddit_score, full_at=2000)
    return reddit


def _international_score(signals: Signals) -> float:
    return _log_scale(signals.reddit_score, full_at=2000)


# --- メイン -----------------------------------------------------------
def score_title(title: Title, signals: Signals, cfg: dict) -> Scored:
    w = cfg["weights"]

    x_buzz = _log_scale(signals.x_engagement, full_at=50000)
    reddit = _log_scale(signals.reddit_score, full_at=2000)
    trends = float(signals.trends_value) if signals.trends_value is not None else 0.0
    editorial = _editorial_score(title, cfg)
    genre = _genre_score(title, cfg)
    scarcity = _scarcity_score(title)
    collector = _collector_score(signals)
    international = _international_score(signals)

    virality = _weighted(
        {"x_buzz": x_buzz, "reddit": reddit, "trends": trends,
         "editorial": editorial, "genre": genre},
        w["virality"],
    )

    adaptation = _weighted(
        {"virality": virality, "editorial": editorial,
         "genre": genre, "international": international},
        w["adaptation"],
    )

    resale = _weighted(
        {"adaptation": adaptation, "scarcity": scarcity, "collector": collector},
        w["resale"],
    )

    scored = Scored(
        title=title,
        signals=signals,
        virality=round(virality, 1),
        adaptation=round(adaptation, 1),
        resale=round(resale, 1),
    )
    _apply_recommendation(scored, cfg)
    _build_rationale(scored, cfg,
                     x_buzz, reddit, trends, editorial, genre, scarcity, collector)
    return scored


def _apply_recommendation(s: Scored, cfg: dict) -> None:
    th = cfg["thresholds"]
    qty = cfg["buy_quantity"]
    if s.resale >= th["buy"] and s.adaptation >= th["watch"]:
        s.recommendation = "BUY"
        if s.resale >= 85:
            s.confidence, s.buy_quantity = "high", qty["high"]
        elif s.resale >= 77:
            s.confidence, s.buy_quantity = "medium", qty["medium"]
        else:
            s.confidence, s.buy_quantity = "low", qty["low"]
    elif s.resale >= th["watch"]:
        s.recommendation = "WATCH"
        s.confidence = "low"
    else:
        s.recommendation = "SKIP"
        s.confidence = "low"


def _build_rationale(s: Scored, cfg: dict, x_buzz, reddit, trends,
                     editorial, genre, scarcity, collector) -> None:
    r = s.rationale
    if s.signals.sources_failed:
        r.append(
            f"⚠️ 取得できなかったデータ源: {', '.join(s.signals.sources_failed)}"
            "（その分スコアの信頼度は低下しています）"
        )
    r.append(f"バズ: X={x_buzz:.0f} / Reddit={reddit:.0f} / Trends={trends:.0f}")
    r.append(f"編集部プッシュ(媒体): {editorial:.0f}（{s.title.platform}）")
    r.append(f"ジャンル追い風: {genre:.0f}（{s.title.genre}）")
    r.append(
        f"初版希少性: {scarcity:.0f}"
        + ("（新人初連載で希少化期待）" if s.title.new_author else "")
    )
    if s.recommendation == "BUY":
        r.append(
            f"→ 初版・未開封を {s.buy_quantity}冊 積み増し推奨"
            f"（confidence={s.confidence}）。発売タイミングで確保。"
        )
    elif s.recommendation == "WATCH":
        r.append("→ 現状はウォッチ。アニメ化発表等のカタリスト待ち。")
    else:
        r.append("→ 現状の10倍転売妙味は低い。見送り推奨。")
