"""スコアリングの基本動作テスト."""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Title, Signals  # noqa: E402
from src import scoring  # noqa: E402


def _cfg():
    with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
              encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_log_scale_bounds():
    assert scoring._log_scale(0, 1000) == 0.0
    assert scoring._log_scale(None, 1000) == 0.0
    assert 0 < scoring._log_scale(1000, 1000) <= 100.0


def test_hot_new_author_gets_buy():
    """強媒体・追い風ジャンル・新人・高バズ → BUY になるはず。"""
    cfg = _cfg()
    t = Title(title="超話題作", platform="週刊少年ジャンプ",
              genre="ダークファンタジー", new_author=True, color_opening=True)
    sig = Signals(x_engagement=80000, reddit_score=5000, trends_value=90,
                  sources_used=["X", "Reddit", "Trends"])
    s = scoring.score_title(t, sig, cfg)
    assert s.recommendation == "BUY"
    assert s.buy_quantity > 0
    assert 0 <= s.resale <= 100


def test_weak_title_skips():
    """弱媒体・無風ジャンル・無名・無バズ → SKIP のはず。"""
    cfg = _cfg()
    t = Title(title="無風作", platform="その他Web", genre="日常", new_author=False)
    sig = Signals(x_engagement=0, reddit_score=0, trends_value=0)
    s = scoring.score_title(t, sig, cfg)
    assert s.recommendation == "SKIP"


def test_scarcity_favors_new_author():
    new = scoring._scarcity_score(Title(title="a", new_author=True))
    vet = scoring._scarcity_score(Title(title="b", new_author=False))
    assert new > vet


if __name__ == "__main__":
    test_log_scale_bounds()
    test_hot_new_author_gets_buy()
    test_weak_title_skips()
    test_scarcity_favors_new_author()
    print("OK: all tests passed")
