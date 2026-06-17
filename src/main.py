"""パイプライン本体: 収集 → スコアリング → レポート → 通知.

実行: python -m src.main [--config config.yaml] [--no-email] [--titles data/seed_titles.yaml]
"""
from __future__ import annotations

import argparse
import logging
import sys

import yaml

from .models import Title, Signals
from .collectors import x_collector, reddit_collector, trends_collector, discovery
from . import scoring, report, notify, synthesize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_signals(title: Title, cfg: dict) -> Signals:
    sig = Signals()

    x = x_collector.collect(title, cfg.get("x_search", {}))
    if x is not None:
        sig.x_engagement = x["engagement"]
        sig.x_tweet_count = x["tweet_count"]
        sig.sources_used.append("X")
    else:
        sig.sources_failed.append("X")

    rd = reddit_collector.collect(title, cfg.get("reddit", {}))
    if rd is not None:
        sig.reddit_score = rd["score"]
        sig.reddit_posts = rd["posts"]
        sig.sources_used.append("Reddit")
    else:
        sig.sources_failed.append("Reddit")

    tr = trends_collector.collect(title, cfg.get("trends", {}))
    if tr is not None:
        sig.trends_value = tr
        sig.sources_used.append("Trends")
    else:
        sig.sources_failed.append("Trends")

    return sig


def run(config_path: str, titles_path: str, notify_on: bool,
        do_discover: bool) -> int:
    cfg = load_yaml(config_path)

    if do_discover:
        candidates = discovery.discover(cfg)
        added = discovery.merge_into_seed(candidates, titles_path)
        log.info("自動発見: 候補%d件 / 新規追記%d件", len(candidates), added)

    raw = load_yaml(titles_path)
    titles = [Title.from_dict(t) for t in raw.get("titles", [])]
    if not titles:
        log.error("監視対象の作品がありません (%s)", titles_path)
        return 1

    log.info("%d作品を判定します", len(titles))
    scored = []
    for t in titles:
        sig = collect_signals(t, cfg)
        scored.append(scoring.score_title(t, sig, cfg))

    scored.sort(key=lambda s: s.resale, reverse=True)

    summary = synthesize.summarize(scored, cfg)
    md = report.build_markdown(scored, cfg, summary)
    path = report.save(md, cfg)
    log.info("レポート保存: %s", path)

    if notify_on:
        html = report.build_html(md, cfg)
        digest = notify.build_digest(scored, cfg)
        n_buy = sum(1 for s in scored if s.recommendation == "BUY")
        subject = f"[マンガせどり] {cfg['report']['title']} (BUY {n_buy}件)"
        results = notify.dispatch(subject, md, html, digest)
        log.info("通知結果: %s", results)

    # サマリーを標準出力にも（Actionsログ確認用）
    print(md)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="新連載マンガ せどり判定")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--titles", default="data/seed_titles.yaml")
    p.add_argument("--no-notify", action="store_true",
                   help="通知(メール/Discord/LINE)を抑止")
    p.add_argument("--no-discover", action="store_true",
                   help="新連載の自動発見をスキップ")
    args = p.parse_args()
    sys.exit(run(args.config, args.titles,
                 notify_on=not args.no_notify,
                 do_discover=not args.no_discover))


if __name__ == "__main__":
    main()
