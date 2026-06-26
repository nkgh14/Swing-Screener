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

# ---- Trend filter: MAs must be stacked and sloping higher ----
MA_SHORT  = 20
MA_MID    = 50
MA_LONG   = 200
# How many days back to compare each MA against itself to check slope
MA_SLOPE_LOOKBACK = 10

# ---- Volatility filter: Average Daily Range must meet minimum ----
# ADR = average of (high - low) / close over the last 20 days
ADR_LOOKBACK = 20
ADR_MIN_PCT  = 3.5   # minimum ADR percentage

# ---- Tight consolidation filter ----
# Recent ATR (last CONSOLIDATION_RECENT days) must be this fraction or less
# of the prior ATR (prior CONSOLIDATION_PRIOR days). Lower = tighter.
CONSOLIDATION_RECENT = 10
CONSOLIDATION_PRIOR  = 30
CONSOLIDATION_MAX_RATIO = 0.75   # recent ATR / prior ATR must be <= this

# ---- Volume confirmation ----
VOLUME_SURGE_LOOKBACK    = 20    # compare today's volume to this many days' average
VOLUME_SURGE_MULTIPLIER  = 1.5   # today's volume must be at least this many times the average

# ---- News ----
NEWS_LOOKBACK_DAYS = 2   # how far back to pull news for flagged stocks

# ---- Email ----
EMAIL_FROM = "NKRAJISNIK2@gmail.com"
EMAIL_TO   = "NKRAJISNIK2@gmail.com"
EMAIL_SUBJECT_PREFIX = "Swing Screener"
