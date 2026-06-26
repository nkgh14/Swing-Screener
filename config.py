"""
Configuration for the swing trading screener.
Edit these values to change what the screener looks for.
"""

# ---- Universe ----
# Full S&P 500 fetched fresh each run from a free, no-key CSV.
# If the fetch fails for any reason the screener falls back to this
# hardcoded list so a network hiccup doesn't abort the whole run.
SP500_CSV_URL = (
    "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers"
    "/main/tickers/sp500.csv"
)

FALLBACK_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD",
    "NFLX", "CRM", "ADBE", "AVGO", "QCOM", "INTC", "CSCO", "ORCL",
    "JPM", "GS", "V", "MA",
    "XOM", "CVX",
    "JNJ", "CEG", "UNH",
    "WMT", "COST", "HD", "NKE",
    "DIS", "BA",
    "SPY", "QQQ", "UUUU",
]

# Max symbols per Alpaca get_stock_bars call. No hard documented limit,
# but 100 keeps response payloads manageable and avoids silent timeouts.
ALPACA_BATCH_SIZE = 100

# ---- Liquidity / quality filters ----
MIN_PRICE      = 10.0       # ignore anything below this price
MIN_AVG_VOLUME = 500_000    # 20-day average daily volume must be at least this

# ---- Criterion 1: MA stack and slope ----
# Price must be above MA20 > MA50 > MA200, and each MA must be higher
# than it was MA_SLOPE_LOOKBACK trading days ago.
MA_SHORT         = 20
MA_MID           = 50
MA_LONG          = 200
MA_SLOPE_LOOKBACK = 10

# ---- Criterion 2: Higher highs and higher lows (rolling) ----
# The highest high of the last HH_HL_WINDOW days must exceed the highest
# high of the HH_HL_WINDOW days before that. Same check for the lows.
# Because the window slides forward each day, this signal refreshes daily.
HH_HL_WINDOW = 10

# ---- Criterion 3: Average Daily Range ----
# ADR = average of (high - low) / close over the last ADR_LOOKBACK days.
# Stock must clear ADR_MIN_PCT to confirm it actually moves enough to trade.
ADR_LOOKBACK = 20
ADR_MIN_PCT  = 3.0   # percent

# ---- Criterion 4: Tightening price action ----
# Today's range as a % of close must be LESS than this fraction of the
# 20-day ADR. A reading below the threshold signals price contraction
# (weaker holders shaken out, potential coiling before continuation).
TODAY_RANGE_TIGHTENING_RATIO = 0.60

# ---- Historical volatility filter (hard gate, applied in pass 2) ----
# Over 3 years of daily data, at least this fraction of rolling 10-day
# windows must have shown a high-to-low swing of 10%+ relative to the
# window's opening price. Keeps only stocks with a track record of moving.
# This is a measure of historical capability — not a prediction.
HIST_VOL_WINDOW        = 10
HIST_VOL_SWING_MIN     = 0.10   # 10% swing threshold per window
HIST_VOL_MIN_PASS_RATE = 0.25   # at least 25% of windows must clear it

# ---- Volume confirmation (informational, not a hard filter) ----
VOLUME_SURGE_LOOKBACK   = 20
VOLUME_SURGE_MULTIPLIER = 1.5

# ---- News ----
NEWS_LOOKBACK_DAYS = 2

# ---- Email ----
EMAIL_FROM           = "NKRAJISNIK2@gmail.com"
EMAIL_TO             = "NKRAJISNIK2@gmail.com"
EMAIL_SUBJECT_PREFIX = "Swing Screener"
