"""メール通知 (SMTP).

必要な環境変数:
  SMTP_HOST   例: smtp.gmail.com
  SMTP_PORT   例: 587
  SMTP_USER   送信元アドレス
  SMTP_PASS   アプリパスワード（Gmailなら2段階認証+アプリパスワード）
  REPORT_TO   送信先（カンマ区切りで複数可）。未設定なら SMTP_USER 宛。
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_email(subject: str, markdown_body: str, html_body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    to = os.environ.get("REPORT_TO", user or "")

    if not (host and user and password and to):
        log.warning("SMTP系の環境変数が未設定のためメール送信をスキップ")
        return False

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
