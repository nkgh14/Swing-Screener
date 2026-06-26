"""
emailer.py

Formats the screener results into a readable email and sends it via
Gmail's SMTP server using an app password (never your real Gmail password).

Sends an email EVERY run, even when nothing was flagged - this is
intentional. Silence is how you'd miss a broken/failed run, so a
"0 results today" email is your confirmation that the bot is alive.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def _fmt_chg(v):
    return f"+{v}%" if v >= 0 else f"{v}%"


def _badge(setup):
    label = "Uptrend + tight"
    return (
        f'<span style="background:#dcfce7;color:#166534;font-size:12px;'
        f'font-weight:600;padding:3px 10px;border-radius:12px;'
        f'white-space:nowrap;">{label}</span>'
    )


def _metric_box(label, value, highlight=False):
    bg = "#fef3c7" if highlight else "#f1f5f9"
    color = "#92400e" if highlight else "#1e293b"
    label_color = "#92400e" if highlight else "#64748b"
    return (
        f'<td style="width:33%;padding:0 4px;">'
        f'<div style="background:{bg};border-radius:6px;padding:8px 10px;text-align:center;">'
        f'<div style="font-size:11px;color:{label_color};margin-bottom:3px;">{label}</div>'
        f'<div style="font-size:15px;font-weight:600;color:{color};">{value}</div>'
        f'</div></td>'
    )


def _card(r):
    vol_pct = r.get("vol_pct")
    vol_str = f"{vol_pct}%" if vol_pct is not None else "n/a"
    vol_high = vol_pct is not None and vol_pct > 70

    setup_badges = " ".join(_badge(s) for s in r["setups"])

    tight_str = f"{r['tightening_ratio']}x ADR"
    metrics = (
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">'
        "<tr>"
        + _metric_box("ADR (20d)", f"{r['adr']}%")
        + _metric_box("Today range", f"{r['today_range_pct']}%  ({tight_str})")
        + _metric_box("Hist. vol", vol_str, highlight=vol_high)
        + "</tr></table>"
    )

    news_items = r.get("news", [])
    if news_items:
        news_rows = "".join(
            f'<tr><td style="padding:3px 0;font-size:13px;color:#1e293b;">'
            f'&bull; <a href="{item["url"]}" style="color:#2563eb;text-decoration:none;">'
            f'{item["headline"]}</a></td></tr>'
            for item in news_items
        )
        news_html = (
            '<div style="margin-top:10px;border-top:1px solid #e2e8f0;padding-top:10px;">'
            '<div style="font-size:11px;color:#64748b;margin-bottom:6px;text-transform:uppercase;'
            'letter-spacing:0.05em;">Recent news</div>'
            f"<table width='100%' cellpadding='0' cellspacing='0'>{news_rows}</table>"
            "</div>"
        )
    else:
        news_html = (
            '<div style="margin-top:10px;border-top:1px solid #e2e8f0;padding-top:10px;'
            'font-size:12px;color:#94a3b8;">No recent news found</div>'
        )

    change_str = (
        f'<span style="font-size:12px;color:#64748b;margin-left:10px;">'
        f'1d&nbsp;{_fmt_chg(r["change_1d"])}&nbsp;&nbsp;'
        f'5d&nbsp;{_fmt_chg(r["change_5d"])}'
        f'</span>'
    )

    ma_str = (
        f'<div style="font-size:11px;color:#94a3b8;margin-top:3px;">'
        f'MA20 {r["ma20"]} &nbsp;·&nbsp; MA50 {r["ma50"]} &nbsp;·&nbsp; MA200 {r["ma200"]}'
        f'</div>'
    )

    return (
        '<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;'
        'padding:16px 20px;margin-bottom:16px;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td><span style="font-size:20px;font-weight:700;color:#0f172a;">{r["symbol"]}</span>'
        f'<span style="font-size:16px;color:#475569;margin-left:10px;">${r["price"]}</span>'
        f'{change_str}{ma_str}</td>'
        f'<td style="text-align:right;white-space:nowrap;vertical-align:top;">{setup_badges}</td>'
        '</tr></table>'
        f'{metrics}'
        f'{news_html}'
        '</div>'
    )


def format_email_body(flagged_results, error=None):
    today = datetime.now().strftime("%Y-%m-%d")

    outer_open = (
        '<div style="background:#f8fafc;padding:24px;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:600px;margin:0 auto;">'
    )
    outer_close = "</div></div>"

    if error:
        body = (
            f'<h2 style="color:#dc2626;font-size:18px;margin:0 0 12px;">Screener run failed — {today}</h2>'
            f'<pre style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;'
            f'padding:12px;font-size:13px;color:#7f1d1d;white-space:pre-wrap;">{error}</pre>'
            f'<p style="color:#64748b;font-size:13px;">Check the GitHub Actions log for details.</p>'
        )
        return outer_open + body + outer_close

    header = (
        f'<h1 style="font-size:22px;font-weight:700;color:#0f172a;margin:0 0 4px;">Swing screener</h1>'
        f'<p style="font-size:14px;color:#64748b;margin:0 0 20px;">{today}</p>'
    )

    if not flagged_results:
        body = (
            header
            + '<p style="color:#475569;font-size:15px;">No symbols matched today\'s criteria.</p>'
            + '<p style="font-size:12px;color:#94a3b8;">(This email confirms the bot ran successfully.)</p>'
        )
        return outer_open + body + outer_close

    summary = (
        f'<p style="font-size:15px;color:#475569;margin:0 0 20px;">'
        f'{len(flagged_results)} match{"es" if len(flagged_results) != 1 else ""} today</p>'
    )

    cards = "".join(_card(r) for r in flagged_results)

    disclaimer = (
        '<p style="font-size:12px;color:#94a3b8;margin-top:20px;border-top:1px solid #e2e8f0;'
        'padding-top:16px;">This is a screening tool, not trading advice. '
        'Verify everything yourself before acting on it.</p>'
    )

    return outer_open + header + summary + cards + disclaimer + outer_close


def send_email(flagged_results=None, error=None):
    """
    Sends the results (or an error report) via Gmail SMTP.
    Credentials come from environment variables:
        GMAIL_ADDRESS    - the Gmail account sending the email
        GMAIL_APP_PASSWORD - a 16-character app password (NOT your normal password)
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    today = datetime.now().strftime("%Y-%m-%d")
    subject_suffix = "FAILED" if error else (
        f"{len(flagged_results)} hit(s)" if flagged_results else "no matches"
    )
    subject = f"{config.EMAIL_SUBJECT_PREFIX} {today} - {subject_suffix}"

    body = format_email_body(flagged_results, error=error)

    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = config.EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, config.EMAIL_TO, msg.as_string())
