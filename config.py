"""
Configuration for the swing trading screener.
Edit these values to change what the screener looks for.
"""

# ---- Universe: which stocks to scan ----
# Start with a manageable list. You can expand this later.
# Tip: keep it under ~100 symbols on the free Alpaca/Finnhub tiers to avoid rate limits.
WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD",
    "NFLX", "CRM", "ADBE", "AVGO", "QCOM", "INTC", "CSCO", "ORCL",
    "JPM", "UUUU", "GS", "V", "MA",
    "XOM", "CVX",
    "JNJ", "CEG", "UNH",
    "WMT", "COST", "HD", "NKE",
    "DIS", "BA",
    "SPY", "QQQ",  # ETFs are fine on Alpaca even though we filter to "US stocks" broadly
]

# ---- Liquidity / quality filters (avoid junk/illiquid names) ----
MIN_PRICE = 10.0           # ignore anything below this price
MIN_AVG_VOLUME = 500_000   # 20-day average daily volume must be at least this

# ---- Trend filter ----
# Stock must be above its 50-day MA, and 50-day MA above 200-day MA, to count as "uptrend"
TREND_LOOKBACK_SHORT = 50
TREND_LOOKBACK_LONG = 200

# ---- Momentum filters (the two setups, flagged separately) ----
RSI_PERIOD = 14

# Setup A: Pullback in an uptrend
PULLBACK_RSI_MIN = 40
PULLBACK_RSI_MAX = 60

# Setup B: Oversold bounce
# Today's RSI must cross back above this level after being below it
OVERSOLD_RSI_THRESHOLD = 30

# ---- Volume confirmation ----
VOLUME_SURGE_LOOKBACK = 20      # compare today's volume to this many days' average
VOLUME_SURGE_MULTIPLIER = 1.5   # today's volume must be at least this many times the average

# ---- News ----
NEWS_LOOKBACK_DAYS = 2   # how far back to pull news for flagged stocks

# ---- Email ----
EMAIL_FROM = "NKRAJISNIK2@gmail.com"
EMAIL_TO = "NKRAJISNIK2@gmail.com"     # can be the same address, or a different one
EMAIL_SUBJECT_PREFIX = "Swing Screener"
