"""Claude による定性サマリー生成（任意）.

環境変数 ANTHROPIC_API_KEY があり config.claude.enabled が true のときだけ動く。
スコアの数字に、過去事例を踏まえた自然言語の総評を1段足す役割。
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from .models import Scored

log = logging.getLogger(__name__)


def summarize(scored: list[Scored], cfg: dict) -> Optional[str]:
    ccfg = cfg.get("claude", {})
    if not ccfg.get("enabled"):
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY 未設定のため定性サマリーをスキップ")
        return None

    try:
        import anthropic
    except ImportError:
        log.info("anthropic 未インストールのため定性サマリーをスキップ")
        return None

    top = scored[:10]
    rows = "\n".join(
        f"- {s.title.title}（{s.title.platform}/{s.title.genre}）"
        f" resale={s.resale} adapt={s.adaptation} viral={s.virality}"
        f" 判定={s.recommendation}"
        for s in top
    )
    prompt = (
        "あなたはマンガ市場とコレクター相場に詳しいアナリストです。"
        "以下は本日の新連載マンガのスコアリング結果です。"
        "過去のアニメ化・初版プレミア化事例（呪術廻戦/SPY×FAMILY/ダンダダン等）も踏まえ、"
        "『今日の注目作と、初版を積み増す価値がある作品』を3〜5行で総評してください。"
        "断定や投資助言は避け、確率的な見立てとして述べること。\n\n"
        f"{rows}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=ccfg.get("model", "claude-sonnet-4-6"),
            max_tokens=int(ccfg.get("max_tokens", 1500)),
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
    except Exception as e:
        log.warning("Claude サマリー生成失敗: %s", e)
        return None
