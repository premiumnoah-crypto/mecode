"""新連載マンガの自動発見.

設定されたニュースフィード(RSS)を取得し、「新連載」「連載開始」等のキーワードを
含む記事タイトルから作品名候補を抽出する。抽出した候補は seed_titles.yaml に
重複しないものだけ追記される（メタデータは"不明"で入るので、後で人手の補強推奨）。

フィードに到達できない/解析できない場合は静かに空を返す（pipelineは継続）。
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

log = logging.getLogger(__name__)

_UA = "mecode-manga-resale-analyzer/1.0"

# 「『作品名』...新連載/連載開始/連載スタート」のような並びから作品名を拾う
_TITLE_PAT = re.compile(r"[「『]([^」』]{1,40})[」』]")


def _fetch_feed(url: str) -> list[str]:
    """RSS/Atom を取得し、エントリのタイトル文字列リストを返す。"""
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as e:
        log.warning("フィード取得失敗 (%s): %s", url, e)
        return []

    titles: list[str] = []
    # RSS 2.0: channel/item/title, Atom: entry/title
    for tag in (".//item/title", ".//{http://www.w3.org/2005/Atom}entry/"
                "{http://www.w3.org/2005/Atom}title"):
        for el in root.iterfind(tag):
            if el.text:
                titles.append(el.text.strip())
    return titles


def discover(cfg: dict) -> list[str]:
    """新連載と思しき作品名候補のリストを返す（重複除去済み）。"""
    dcfg = cfg.get("discovery", {})
    if not dcfg.get("enabled"):
        return []

    keywords = dcfg.get("keywords", ["新連載", "連載開始", "連載スタート"])
    sources = dcfg.get("sources", [])
    found: set[str] = set()

    for url in sources:
        for headline in _fetch_feed(url):
            if not any(k in headline for k in keywords):
                continue
            for m in _TITLE_PAT.findall(headline):
                name = m.strip()
                # ノイズ除去（号数・誌名など極端に短い/記号のみは除外）
                if len(name) >= 2 and not name.isdigit():
                    found.add(name)

    if found:
        log.info("新連載候補を %d件 発見: %s", len(found), ", ".join(sorted(found)))
    return sorted(found)


def merge_into_seed(candidates: list[str], seed_path: str) -> int:
    """候補を seed_titles.yaml に重複なく追記。追加した件数を返す。"""
    import yaml

    if not candidates:
        return 0
    with open(seed_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    titles = data.get("titles") or []
    existing = {t.get("title") for t in titles if isinstance(t, dict)}

    added = 0
    for name in candidates:
        if name in existing:
            continue
        titles.append({
            "title": name,
            "platform": "不明",
            "genre": "不明",
            "new_author": False,
            "color_opening": False,
            "search_terms": [],
        })
        existing.add(name)
        added += 1

    if added:
        data["titles"] = titles
        with open(seed_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        log.info("seed_titles.yaml に %d件 追記", added)
    return added
