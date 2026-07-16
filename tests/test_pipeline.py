"""発見マージ・通知ダイジェストのオフラインテスト."""
import os
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors import discovery  # noqa: E402
from src.collectors.discovery import _TITLE_PAT  # noqa: E402
from src.models import Title, Signals, Scored  # noqa: E402
from src import notify, report  # noqa: E402
import json as _json  # noqa: E402


def test_title_extraction_from_headline():
    h = "新人作家の話題作『すごい新連載』がジャンプ+で連載開始"
    names = _TITLE_PAT.findall(h)
    assert "すごい新連載" in names


def test_merge_into_seed_dedup():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f:
        yaml.safe_dump({"titles": [{"title": "既存作"}]}, f, allow_unicode=True)
        path = f.name
    try:
        added = discovery.merge_into_seed(["既存作", "新規作A", "新規作B"], path)
        assert added == 2  # 既存作はスキップされる
        data = yaml.safe_load(open(path, encoding="utf-8"))
        titles = {t["title"] for t in data["titles"]}
        assert {"既存作", "新規作A", "新規作B"} <= titles
        # 再実行で増えない
        assert discovery.merge_into_seed(["新規作A"], path) == 0
    finally:
        os.unlink(path)


def test_digest_lists_buys():
    cfg = {"report": {"title": "テスト"}}
    s = Scored(title=Title(title="買い作", platform="ジャンプ+"),
               signals=Signals(), resale=88.0, recommendation="BUY",
               buy_quantity=10, confidence="high")
    digest = notify.build_digest([s], cfg)
    assert "買い作" in digest
    assert "10冊" in digest


def test_build_json_shape():
    cfg = {"report": {"title": "テスト", "timezone": "Asia/Tokyo"}}
    s = Scored(title=Title(title="作品X", platform="ジャンプ+"),
               signals=Signals(sources_used=["X"], sources_failed=["Reddit"]),
               virality=10.0, adaptation=20.0, resale=30.0,
               recommendation="WATCH")
    data = report.build_json([s], cfg, summary="総評")
    # フロントが依存するキーが揃っていること
    assert data["schema_version"] == 1
    assert data["count"] == 1
    assert data["items"][0]["scores"]["resale"] == 30.0
    assert data["items"][0]["recommendation"] == "WATCH"
    # JSON直列化できること（日本語含む）
    _json.loads(_json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    test_title_extraction_from_headline()
    test_merge_into_seed_dedup()
    test_digest_lists_buys()
    test_build_json_shape()
    print("OK: pipeline tests passed")
