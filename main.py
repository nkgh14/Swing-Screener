"""
main.py

The single entry point for the daily run. This is the script GitHub
Actions will execute on a schedule.

Flow:
  1. Run the technical screener against the watchlist
  2. Attach recent news to whatever got flagged
  3. Email the results (or email an error report if anything broke)

Wrapped in a broad try/except so that ANY failure still results in an
email being sent - silent failures are the main risk with unattended
scheduled jobs, so we email errors out rather than letting them vanish
into a GitHub Actions log nobody looks at.
"""

import traceback

from screener import run_screen
from news import attach_news_to_results
from emailer import send_email


def main():
    try:
        flagged = run_screen()
        flagged = attach_news_to_results(flagged)
        send_email(flagged_results=flagged)
        print(f"Run complete. {len(flagged)} symbol(s) flagged. Email sent.")
    except Exception:
        error_text = traceback.format_exc()
        print("Run failed with an error:")
        print(error_text)
        try:
            send_email(error=error_text)
        except Exception:
            # If even the error email fails, at least the GitHub Actions
            # log will show the failure (and the job itself will show red).
            print("Additionally failed to send the error notification email.")
            raise


if __name__ == "__main__":
    main()
