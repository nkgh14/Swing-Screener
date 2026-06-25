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


def format_email_body(flagged_results, error=None):
    today = datetime.now().strftime("%Y-%m-%d")

    if error:
        return f"Screener run on {today} FAILED with an error:\n\n{error}\n\nCheck the GitHub Actions log for details."

    if not flagged_results:
        return f"Screener run on {today}: no symbols matched today's criteria.\n\n(This email confirms the bot ran successfully.)"

    lines = [f"Screener run on {today}: {len(flagged_results)} symbol(s) matched.\n"]

    pullback_hits = [r for r in flagged_results if "pullback" in r["setups"]]
    bounce_hits = [r for r in flagged_results if "oversold_bounce" in r["setups"]]

    def format_result_block(r):
        block = [
            f"  {r['symbol']}  —  ${r['price']}  (RSI {r['rsi']})",
            f"    50-day MA: {r['ma50']}   200-day MA: {r['ma200']}",
            f"    Volume: {r['volume_ratio']}x 20-day average"
            + (" [CONFIRMED]" if r["volume_confirmed"] else " [below threshold]"),
        ]
        news = r.get("news", [])
        if news:
            block.append("    Recent news:")
            for item in news:
                block.append(f"      - ({item['source']}, {item['datetime']}) {item['headline']}")
                block.append(f"        {item['url']}")
        else:
            block.append("    Recent news: none found")
        return "\n".join(block)

    if pullback_hits:
        lines.append(f"\n--- Pullback in Uptrend ({len(pullback_hits)}) ---")
        for r in pullback_hits:
            lines.append(format_result_block(r))

    if bounce_hits:
        lines.append(f"\n--- Oversold Bounce ({len(bounce_hits)}) ---")
        for r in bounce_hits:
            lines.append(format_result_block(r))

    lines.append(
        "\n\nReminder: this is a screening tool, not trading advice. "
        "Verify everything yourself before acting on it."
    )

    return "\n".join(lines)


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
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, config.EMAIL_TO, msg.as_string())
