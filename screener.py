"""
screener.py

Screens the S&P 500 universe (fetched fresh each run) using a two-pass
architecture:

  Pass 1 — cheap checks against already-fetched daily bars (~500 symbols):
    1. MA stack + slope : price > MA20 > MA50 > MA200, all three sloping up
    2. Higher highs/lows: rolling 10-day HH and HL both printing higher
    3. ADR >= 3%        : average daily range confirms the stock is moving
    4. Tightening today : today's range is < 60% of the 20-day ADR average

  Pass 2 — expensive per-symbol fetches, only on pass-1 survivors:
    5. Historical vol   : >= 25% of rolling 10-day windows (3 yrs) had 10%+ swing

This module has NO side effects (no emailing, no printing).
"""

import io
import os
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def fetch_sp500_symbols():
    """
    Downloads the S&P 500 ticker list from a free GitHub-hosted CSV and
    returns a plain list of Alpaca-compatible symbol strings.

    Normalises share-class tickers: the CSV uses BRK.B style dots;
    Alpaca's IEX feed expects BRK/B style slashes (single trailing letter
    after the dot, e.g. .A or .B).

    Falls back to config.FALLBACK_WATCHLIST on any error so a network
    hiccup doesn't abort the whole run.
    """
    try:
        resp = requests.get(config.SP500_CSV_URL, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))

        # Accept a "Symbol" column or fall back to the first column
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        raw = df[col].dropna().str.strip().tolist()

        symbols = []
        for s in raw:
            # BRK.B → BRK/B, BF.B → BF/B (single letter after the dot only)
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 1:
                s = f"{parts[0]}/{parts[1]}"
            symbols.append(s)

        logger.info("Fetched %d S&P 500 symbols from CSV.", len(symbols))
        return symbols

    except Exception as exc:
        logger.warning(
            "Failed to fetch S&P 500 CSV (%s). Using fallback watchlist.", exc
        )
        return list(config.FALLBACK_WATCHLIST)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def get_alpaca_client():
    api_key    = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(api_key, secret_key)


def fetch_daily_bars(client, symbols, lookback_days=300):
    """
    Pulls daily OHLCV bars for all symbols, batching requests to stay within
    practical payload limits (config.ALPACA_BATCH_SIZE symbols per call).

    Returns { "AAPL": DataFrame, "MSFT": DataFrame, ... }.
    Symbols with no data come back as None.
    """
    # End 1 day back — free IEX tier rejects requests that reach into today.
    end   = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=lookback_days)

    result = {}

    for batch_start in range(0, len(symbols), config.ALPACA_BATCH_SIZE):
        batch = symbols[batch_start : batch_start + config.ALPACA_BATCH_SIZE]

        try:
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX,
            )
            df_all = client.get_stock_bars(request).df
        except Exception as exc:
            logger.warning("Batch %d-%d failed: %s", batch_start,
                           batch_start + len(batch), exc)
            for s in batch:
                result[s] = None
            continue

        for symbol in batch:
            try:
                df = df_all.loc[symbol].copy()
                df.index = pd.to_datetime(df.index)
                result[symbol] = df.sort_index()
            except KeyError:
                result[symbol] = None

    return result


def fetch_volatility_bars(client, symbol):
    """3 years of daily bars for the historical volatility calculation."""
    end   = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=3 * 365)

    try:
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        df = client.get_stock_bars(request).df.loc[symbol].copy()
        df.index = pd.to_datetime(df.index)
        return df.sort_index()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def compute_adr(df):
    """
    Average Daily Range over the last ADR_LOOKBACK days, as a percentage
    of the closing price: mean((high - low) / close * 100).
    """
    tail = df.tail(config.ADR_LOOKBACK)
    return float(((tail["high"] - tail["low"]) / tail["close"] * 100).mean())


def compute_volatility_pct(df):
    """
    Fraction of rolling HIST_VOL_WINDOW-day periods (over 3 years of
    history) where the high-to-low swing exceeded HIST_VOL_SWING_MIN
    relative to the window's opening price.

    # This is a measure of historical capability to move 10%+ in 10 trading
    # days — not a prediction that it will happen again.
    """
    window    = config.HIST_VOL_WINDOW
    threshold = config.HIST_VOL_SWING_MIN

    opens = df["open"].values
    highs = df["high"].values
    lows  = df["low"].values
    n     = len(df)

    if n < window:
        return 0.0

    hit   = 0
    total = n - window + 1

    for i in range(total):
        period_open = opens[i]
        if period_open == 0:
            total -= 1
            continue
        swing = (highs[i : i + window].max() - lows[i : i + window].min()) / period_open
        if swing >= threshold:
            hit += 1

    return hit / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Pass-1 filter
# ---------------------------------------------------------------------------

def evaluate_symbol(symbol, df):
    """
    Applies the four cheap price-based criteria to a single symbol.
    Returns a result dict on success, None if any criterion fails.

    Criteria (all four must pass):
      1. MA stack + slope
      2. Rolling higher highs and higher lows
      3. ADR >= ADR_MIN_PCT
      4. Today's range < TODAY_RANGE_TIGHTENING_RATIO * ADR
    """
    min_bars = config.MA_LONG + config.MA_SLOPE_LOOKBACK + config.HH_HL_WINDOW
    if df is None or len(df) < min_bars:
        return None

    close  = df["close"]
    volume = df["volume"]

    latest_price  = float(close.iloc[-1])
    latest_volume = float(volume.iloc[-1])

    # --- Liquidity pre-filter ---
    avg_volume_20 = float(volume.tail(config.VOLUME_SURGE_LOOKBACK).mean())
    if latest_price < config.MIN_PRICE or avg_volume_20 < config.MIN_AVG_VOLUME:
        return None

    # --- Criterion 1: MA stack and slope ---
    ma20  = close.rolling(config.MA_SHORT).mean()
    ma50  = close.rolling(config.MA_MID).mean()
    ma200 = close.rolling(config.MA_LONG).mean()

    ma20_now,  ma20_then  = float(ma20.iloc[-1]),  float(ma20.iloc[-1 - config.MA_SLOPE_LOOKBACK])
    ma50_now,  ma50_then  = float(ma50.iloc[-1]),  float(ma50.iloc[-1 - config.MA_SLOPE_LOOKBACK])
    ma200_now, ma200_then = float(ma200.iloc[-1]), float(ma200.iloc[-1 - config.MA_SLOPE_LOOKBACK])

    stacked = latest_price > ma20_now > ma50_now > ma200_now
    sloping = ma20_now > ma20_then and ma50_now > ma50_then and ma200_now > ma200_then

    if not (stacked and sloping):
        return None

    # --- Criterion 2: Rolling higher highs and higher lows ---
    # Most recent HH_HL_WINDOW days vs the HH_HL_WINDOW days before that.
    # The window slides forward with each daily run, so the signal is fresh
    # every day (not just every 10 days).
    w = config.HH_HL_WINDOW
    recent_high = float(df["high"].iloc[-w:].max())
    prior_high  = float(df["high"].iloc[-2 * w : -w].max())
    recent_low  = float(df["low"].iloc[-w:].min())
    prior_low   = float(df["low"].iloc[-2 * w : -w].min())

    if not (recent_high > prior_high and recent_low > prior_low):
        return None

    # --- Criterion 3: ADR >= minimum ---
    adr = compute_adr(df)
    if adr < config.ADR_MIN_PCT:
        return None

    # --- Criterion 4: Today's range is tightening ---
    today_range_pct = float(
        (df["high"].iloc[-1] - df["low"].iloc[-1]) / df["close"].iloc[-1] * 100
    )
    tightening_ratio = today_range_pct / adr if adr > 0 else 1.0

    if tightening_ratio >= config.TODAY_RANGE_TIGHTENING_RATIO:
        return None

    # --- Volume confirmation (informational) ---
    volume_ratio     = latest_volume / avg_volume_20 if avg_volume_20 > 0 else 0
    volume_confirmed = volume_ratio >= config.VOLUME_SURGE_MULTIPLIER

    change_1d = round((float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2)
    change_5d = round((float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100, 2)

    return {
        "symbol":           symbol,
        "price":            round(latest_price, 2),
        "change_1d":        change_1d,
        "change_5d":        change_5d,
        "ma20":             round(ma20_now, 2),
        "ma50":             round(ma50_now, 2),
        "ma200":            round(ma200_now, 2),
        "adr":              round(adr, 2),
        "today_range_pct":  round(today_range_pct, 2),
        "tightening_ratio": round(tightening_ratio, 2),
        "volume_ratio":     round(volume_ratio, 2),
        "volume_confirmed": bool(volume_confirmed),
        "setups":           ["uptrend_tight"],
        "vol_pct":          None,   # filled in pass 2
    }


# ---------------------------------------------------------------------------
# Pass-2 filter
# ---------------------------------------------------------------------------

def passes_volatility_filter(client, symbol):
    """
    Hard gate: fetches 3 years of daily bars and checks that at least
    HIST_VOL_MIN_PASS_RATE of rolling 10-day windows had a 10%+ swing.
    Returns (passes: bool, vol_pct: float).
    """
    df = fetch_volatility_bars(client, symbol)
    if df is None or df.empty:
        return False, 0.0
    rate = compute_volatility_pct(df)
    return rate >= config.HIST_VOL_MIN_PASS_RATE, round(rate * 100, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_screen():
    """
    1. Fetch the S&P 500 universe (with fallback).
    2. Fetch ~300 days of daily bars for the full universe in batches.
    3. Pass 1: apply the four cheap criteria to every symbol.
    4. Pass 2: apply the expensive historical volatility gate to survivors.
    5. Return the final flagged list.
    """
    client  = get_alpaca_client()
    symbols = fetch_sp500_symbols()

    logger.info("Fetching daily bars for %d symbols.", len(symbols))
    bars_by_symbol = fetch_daily_bars(client, symbols)

    # Pass 1 — cheap checks
    candidates = []
    for symbol in symbols:
        result = evaluate_symbol(symbol, bars_by_symbol.get(symbol))
        if result is not None:
            candidates.append(result)

    logger.info("Pass 1: %d candidates after price-based filters.", len(candidates))

    # Pass 2 — expensive historical volatility check
    flagged = []
    for result in candidates:
        passes, vol_pct = passes_volatility_filter(client, result["symbol"])
        if passes:
            result["vol_pct"] = vol_pct
            flagged.append(result)

    logger.info("Pass 2: %d symbols passed all filters.", len(flagged))
    return flagged


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_screen()
    if not results:
        print("No symbols matched today.")
    for r in results:
        print(r)
