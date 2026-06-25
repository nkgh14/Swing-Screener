"""
news.py

For symbols flagged by the screener, pulls recent news headlines from
Finnhub so the email shows *why* a stock might be moving, not just that
it matched a technical pattern.

We only call this for flagged symbols (not the whole watchlist) to stay
comfortably within Finnhub's free-tier rate limit.
"""

import os
import time
from datetime import datetime, timedelta

import requests

import config

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


def get_news_for_symbol(symbol, api_key, lookback_days):
    """
    Returns a list of recent news items for a symbol:
        [{"headline": ..., "source": ..., "url": ..., "datetime": ...}, ...]
    Returns an empty list on any failure (a missing news feed shouldn't
    crash the whole screener run).
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    params = {
        "symbol": symbol,
        "from": start_date,
        "to": end_date,
        "token": api_key,
    }

    try:
        response = requests.get(f"{FINNHUB_BASE_URL}/company-news", params=params, timeout=10)
        response.raise_for_status()
        articles = response.json()
    except requests.RequestException:
        return []

    news_items = []
    for article in articles[:5]:  # cap at 5 most recent per symbol
        news_items.append({
            "headline": article.get("headline", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "datetime": datetime.fromtimestamp(article.get("datetime", 0)).strftime("%Y-%m-%d %H:%M"),
        })

    return news_items


def attach_news_to_results(flagged_results):
    """
    Takes the screener's flagged results and adds a 'news' key to each one.
    Mutates and returns the same list for convenience.
    """
    api_key = os.environ["FINNHUB_API_KEY"]

    for result in flagged_results:
        result["news"] = get_news_for_symbol(result["symbol"], api_key, config.NEWS_LOOKBACK_DAYS)
        time.sleep(1)  # stay well under Finnhub's free-tier rate limit

    return flagged_results
