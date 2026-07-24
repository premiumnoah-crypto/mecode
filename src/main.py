"""パイプライン本体: 収集 → スコアリング → レポート → 通知.

実行: python -m src.main [--config config.yaml] [--no-email] [--titles data/seed_titles.yaml]
"""
from __future__ import annotations

import argparse
import logging
import sys

import yaml

from .models import Title, Signals
from .collectors import (
    x_collector, reddit_collector, trends_collector, discovery, anilist,
)
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

    # --- 一次データ源: AniList(キー不要・データセンターIPからも利用可) --------
    # popularity→バズ, favourites→コレクター/海外人気, trending→トレンド に対応付け。
    al = anilist.collect(title, cfg)
    if al is not None:
        sig.x_engagement = al["popularity"]
        sig.reddit_score = al["favourites"]
        sig.trends_value = al["trending_norm"]
        sig.sources_used.append("AniList")
    else:
        sig.sources_failed.append("AniList")

    # --- X(Twitter): トークンがあれば実エンゲージメントで上書き ---------------
    x = x_collector.collect(title, cfg.get("x_search", {}))
    if x is not None:
        sig.x_engagement = x["engagement"]
        sig.x_tweet_count = x["tweet_count"]
        sig.sources_used.append("X")

    # --- Reddit / Google Trends: 自動環境では 403/429 で遮断されるため既定オフ ---
    # (config.yaml で reddit.enabled / trends.enabled を true にすると再有効化)
    if cfg.get("reddit", {}).get("enabled"):
        rd = reddit_collector.collect(title, cfg.get("reddit", {}))
        if rd is not None:
            sig.reddit_score = rd["score"]
            sig.reddit_posts = rd["posts"]
            sig.sources_used.append("Reddit")
        else:
            sig.sources_failed.append("Reddit")

    if cfg.get("trends", {}).get("enabled"):
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
        # 一次: AniList(実在マンガをメタデータ付きで取得)
        al_records = anilist.discover(cfg)
        al_added = anilist.merge_into_seed(al_records, titles_path)
        # 補助: ニュースフィード(natalie等)からの作品名抽出(到達可能なら)
        news_candidates = discovery.discover(cfg)
        news_added = discovery.merge_into_seed(news_candidates, titles_path)
        log.info("自動発見: AniList %d件追記 / ニュース %d件追記",
                 al_added, news_added)

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

    # ブラウザ(フロントエンド)が直接fetchできる機械可読JSONを公開
    data = report.build_json(scored, cfg, summary)
    json_paths = report.save_json(data)
    log.info("JSONデータ公開: %s", ", ".join(json_paths))

    if notify_on:
        # 通知は付随機能。失敗してもデータ生成/コミットを止めないよう握りつぶす。
        try:
            html = report.build_html(md, cfg)
            digest = notify.build_digest(scored, cfg)
            n_buy = sum(1 for s in scored if s.recommendation == "BUY")
            subject = f"[マンガせどり] {cfg['report']['title']} (BUY {n_buy}件)"
            results = notify.dispatch(subject, md, html, digest)
            log.info("通知結果: %s", results)
        except Exception as e:
            log.warning("通知処理でエラー（データ生成は継続）: %s", e)

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
