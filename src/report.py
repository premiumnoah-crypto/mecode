"""レポート生成 (Markdown / HTML)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from .models import Scored

_DISCLAIMER = (
    "※ 本レポートのスコアは過去のヒット要因に基づく確率的な期待値であり、"
    "アニメ化・映画化・転売益を保証するものではありません。"
    "コミックスのせどり・投資は自己責任で行ってください。"
)

_BADGE = {"BUY": "🟢 BUY", "WATCH": "🟡 WATCH", "SKIP": "⚪ SKIP"}


def _date_str(tz_name: str) -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def build_markdown(scored: list[Scored], cfg: dict,
                   summary: Optional[str] = None) -> str:
    rcfg = cfg["report"]
    top = scored[: rcfg.get("top_n", 15)]
    date = _date_str(rcfg.get("timezone", "Asia/Tokyo"))

    buys = [s for s in scored if s.recommendation == "BUY"]

    lines: list[str] = []
    lines.append(f"# {rcfg['title']}")
    lines.append(f"_{date} 生成 / 監視 {len(scored)}作品 / BUY {len(buys)}件_\n")

    if summary:
        lines.append("## 🧠 サマリー")
        lines.append(summary + "\n")

    if buys:
        lines.append("## 🟢 積み増し推奨（BUY）")
        lines.append("| 作品 | 媒体 | resale | adapt | viral | 推奨冊数 | 信頼度 |")
        lines.append("|------|------|-------:|------:|------:|--------:|:------:|")
        for s in buys:
            lines.append(
                f"| **{s.title.title}** | {s.title.platform} | "
                f"{s.resale} | {s.adaptation} | {s.virality} | "
                f"{s.buy_quantity}冊 | {s.confidence} |"
            )
        lines.append("")

    lines.append(f"## 📊 総合ランキング (Top {len(top)})")
    lines.append("| # | 判定 | 作品 | resale | adapt | viral |")
    lines.append("|--:|:----:|------|-------:|------:|------:|")
    for i, s in enumerate(top, 1):
        lines.append(
            f"| {i} | {_BADGE.get(s.recommendation, s.recommendation)} | "
            f"{s.title.title} | {s.resale} | {s.adaptation} | {s.virality} |"
        )
    lines.append("")

    lines.append("## 🔎 詳細・判定根拠")
    for s in top:
        lines.append(
            f"### {_BADGE.get(s.recommendation)} {s.title.title}"
            f"（{s.title.author or '作者不明'} / {s.title.genre}）"
        )
        if s.title.volume1_date:
            lines.append(f"- 1巻発売(予定): **{s.title.volume1_date}**")
        for r in s.rationale:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("---")
    lines.append(f"_{_DISCLAIMER}_")
    return "\n".join(lines)


def build_html(markdown_text: str, cfg: dict) -> str:
    """簡易Markdown→HTML（メール本文用・依存を増やさない最小実装）。"""
    import html
    import re

    out = []
    for line in markdown_text.split("\n"):
        esc = html.escape(line)
        if line.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("|"):
            out.append(f"<tt>{esc}</tt><br>")
        elif line.startswith("- "):
            out.append(f"&nbsp;&nbsp;• {esc[2:]}<br>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip() == "":
            out.append("<br>")
        else:
            out.append(f"{esc}<br>")
    body = "\n".join(out)
    # **bold**
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    return (
        "<html><body style='font-family:sans-serif;line-height:1.5;"
        f"max-width:780px'>{body}</body></html>"
    )


def save(markdown_text: str, cfg: dict) -> str:
    rcfg = cfg["report"]
    save_dir = rcfg.get("save_dir", "reports")
    os.makedirs(save_dir, exist_ok=True)
    date = _date_str(rcfg.get("timezone", "Asia/Tokyo")).split(" ")[0]
    path = os.path.join(save_dir, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    return path
