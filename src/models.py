"""データモデル定義."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Title:
    """監視対象の1作品（seed_titles.yaml の1エントリ）."""

    title: str
    title_en: Optional[str] = None
    author: Optional[str] = None
    platform: str = "不明"
    genre: str = "不明"
    debut_date: Optional[str] = None
    volume1_date: Optional[str] = None
    new_author: bool = False
    color_opening: bool = False
    search_terms: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Title":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Signals:
    """各データ源から集めた生シグナル。取得できなかった源は None のまま。"""

    x_engagement: Optional[float] = None   # いいね+RT+返信+引用の合計
    x_tweet_count: Optional[int] = None
    reddit_score: Optional[float] = None   # upvote+コメントの加重和
    reddit_posts: Optional[int] = None
    trends_value: Optional[float] = None   # 0-100
    sources_used: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


@dataclass
class Scored:
    """1作品のスコアリング結果."""

    title: Title
    signals: Signals
    virality: float = 0.0
    adaptation: float = 0.0
    resale: float = 0.0
    recommendation: str = "SKIP"   # BUY / WATCH / SKIP
    buy_quantity: int = 0
    confidence: str = "low"        # high / medium / low
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
