"""通知ディスパッチ: メール / Discord / LINE.

各チャンネルは対応する環境変数が揃っているときだけ送信される（未設定なら静かにスキップ）。
  メール   : SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, REPORT_TO
  Discord  : DISCORD_WEBHOOK_URL
  LINE     : LINE_CHANNEL_ACCESS_TOKEN, LINE_TO   ※LINE Messaging APIを使用
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

log = logging.getLogger(__name__)


# --- メール ----------------------------------------------------------
def send_email(subject: str, markdown_body: str, html_body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to = os.environ.get("REPORT_TO") or user or ""

    if not (host and user and password and to):
        log.info("SMTP系の環境変数が未設定のためメールをスキップ")
        return False

    # SMTP_PORT は空文字("")で渡ることがある(GitHub Secrets未設定時)ので安全に既定値へ
    port = int((os.environ.get("SMTP_PORT") or "587").strip())

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.attach(MIMEText(markdown_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = [a.strip() for a in to.split(",") if a.strip()]
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
        log.info("メール送信成功: %s", recipients)
        return True
    except Exception as e:
        log.error("メール送信失敗: %s", e)
        return False


# --- Discord ---------------------------------------------------------
def send_discord(text: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        log.info("DISCORD_WEBHOOK_URL 未設定のため Discordをスキップ")
        return False
    # Discordの content 上限は2000文字。超える分は切り詰める。
    body = text if len(text) <= 1900 else text[:1900] + "\n…(以下省略)"
    try:
        r = requests.post(url, json={"content": body}, timeout=20)
        r.raise_for_status()
        log.info("Discord送信成功")
        return True
    except requests.RequestException as e:
        log.error("Discord送信失敗: %s", e)
        return False


# --- LINE (Messaging API) -------------------------------------------
# 注: 旧「LINE Notify」は2025年3月で終了したため、Messaging APIのpushを使用する。
def send_line(text: str) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    to = os.environ.get("LINE_TO")
    if not (token and to):
        log.info("LINE系の環境変数が未設定のため LINEをスキップ")
        return False
    body = text if len(text) <= 4900 else text[:4900] + "\n…(以下省略)"
    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"to": to, "messages": [{"type": "text", "text": body}]},
            timeout=20,
        )
        r.raise_for_status()
        log.info("LINE送信成功")
        return True
    except requests.RequestException as e:
        log.error("LINE送信失敗: %s", e)
        return False


# --- ダイジェスト（チャット系の短文用） --------------------------------
def build_digest(scored: list, cfg: dict) -> str:
    """Discord/LINE向けの短いダイジェストを作る。"""
    buys = [s for s in scored if s.recommendation == "BUY"]
    title = cfg["report"]["title"]
    lines = [f"📚 {title}", f"監視{len(scored)}作品 / BUY {len(buys)}件\n"]
    if buys:
        lines.append("🟢 積み増し推奨:")
        for s in buys[:10]:
            lines.append(
                f"・{s.title.title}（{s.title.platform}）"
                f" resale={s.resale} → {s.buy_quantity}冊 [{s.confidence}]"
            )
    else:
        top = scored[:3]
        lines.append("本日のBUYなし。注目:")
        for s in top:
            lines.append(f"・{s.title.title} resale={s.resale}（{s.recommendation}）")
    lines.append("\n※確率的見立て。投資は自己責任で。")
    return "\n".join(lines)


# --- 一括ディスパッチ ------------------------------------------------
def dispatch(subject: str, markdown_body: str, html_body: str,
             digest: str) -> dict[str, bool]:
    """全チャンネルへ送信し、結果を返す。"""
    return {
        "email": send_email(subject, markdown_body, html_body),
        "discord": send_discord(digest),
        "line": send_line(digest),
    }
